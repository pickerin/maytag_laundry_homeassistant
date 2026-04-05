import asyncio
import os
import aiohttp

from whirlpool.auth import Auth, AccountLockedError
from whirlpool.appliancesmanager import AppliancesManager
from whirlpool.backendselector import BackendSelector, Brand, Region

EMAIL = os.environ["WHIRLPOOL_EMAIL"]
PASSWORD = os.environ["WHIRLPOOL_PASSWORD"]

async def main():
    backend = BackendSelector(Brand.Maytag, Region.US)
    print("auth_url:", backend.oauth_token_url)
    print("client_credentials:", [(c.client_id, c.client_secret[:12] + "...") for c in backend.client_credentials])
    async with aiohttp.ClientSession() as session:
        auth = Auth(backend, EMAIL, PASSWORD, session)

        try:
            ok_auth = await auth.do_auth(store=False)
        except AccountLockedError:
            print("ACCOUNT LOCKED - reset your password at maytag.com to unlock")
            return
        print("do_auth ok:", ok_auth)

        if not ok_auth:
            print("Auth failed, cannot continue")
            return

        acct = await auth.get_account_id()
        print("accountId:", acct)

        mgr = AppliancesManager(backend, auth, session)
        ok = await mgr.fetch_appliances()
        print("fetch_appliances ok:", ok)

        washer_dryers = mgr.washer_dryers or []
        print("washer_dryers len:", len(washer_dryers))
        for a in washer_dryers:
            print(f"  SAID={a['SAID']}  DATA_MODEL={a.get('DATA_MODEL')}  NAME={a.get('NAME')}")

        # Test the same parsing logic used by config_flow
        washers = [a["SAID"] for a in washer_dryers if "washer" in a.get("DATA_MODEL", "").lower()]
        dryers = [a["SAID"] for a in washer_dryers if "dryer" in a.get("DATA_MODEL", "").lower()]
        others = [a["SAID"] for a in (mgr.aircons or []) + (mgr.ovens or []) + (mgr.refrigerators or [])]
        print(f"\nDiscovery result: {len(washers)} washers, {len(dryers)} dryers, {len(others)} others")

        # Try fetching TS_SAID devices directly from the token
        ts_saids = auth.get_said_list()  # This is the SAID field, but TS_SAID is in the JWT
        print(f"\nSAID from auth: {ts_saids}")

        # Decode JWT to get TS_SAID
        import base64, json
        token = auth.get_access_token()
        payload = token.split(".")[1]
        payload += "=" * (4 - len(payload) % 4)  # pad base64
        jwt_data = json.loads(base64.b64decode(payload))
        ts_saids = jwt_data.get("TS_SAID", [])
        print(f"TS_SAID from JWT: {ts_saids}")

        # Get full user details — may contain appliance info
        headers = auth.create_headers()
        base = backend.base_url

        print(f"\n--- getUserDetails ---")
        async with session.get(f"{base}/api/v1/getUserDetails", headers=headers) as r:
            body = await r.text()
            print(f"  status={r.status}")
            print(f"  body={body[:3000]}")

        # Try different API versions and paths for TS appliances
        probe_urls = [
            (f"{base}/api/v1/getAccountDetails", "GET"),
            (f"{base}/api/v1/appliance/all/ts/account/{acct}", "GET"),
            (f"{base}/api/v2/appliance/all/ts/account/{acct}", "GET"),
            (f"{base}/api/v3/appliance/all/ts/account/{acct}", "GET"),
        ]

        for url, method in probe_urls:
            print(f"\nProbing: {url}")
            async with session.get(url, headers=headers) as r:
                body = await r.text()
                print(f"  status={r.status} body={body[:1000]}")

        # Use the library's own aiohttp-based STOMP approach (like EventSocket does)
        import time, re

        ws_url_resp = await session.get(f"{base}/api/v1/client_auth/webSocketUrl", headers=headers)
        ws_data = await ws_url_resp.json()
        ws_url = ws_data["url"]
        token = auth.get_access_token()
        MSG_TERM = "\n\n\0"
        DATA_RE = re.compile(r"\{(.*)\}\x00", re.DOTALL)

        print(f"\n--- STOMP WebSocket test (aiohttp) ---")
        print(f"WS URL: {ws_url}")

        timeout = aiohttp.ClientTimeout(total=None, connect=60)
        async with session.ws_connect(ws_url, timeout=timeout, autoclose=True, autoping=True, heartbeat=45) as ws:
            # CONNECT
            await ws.send_str(f"CONNECT\naccept-version:1.1,1.2\nheart-beat:30000,0\nwcloudtoken:{token}" + MSG_TERM)
            msg = await ws.receive()
            print(f"CONNECT resp: {msg.data[:200] if msg.data else msg}")

            # SUBSCRIBE to each TS SAID
            for i, said in enumerate(ts_saids):
                sub = f"SUBSCRIBE\nid:sub-{i}\ndestination:/topic/{said}\nack:auto" + MSG_TERM
                await ws.send_str(sub)
                print(f"Subscribed to /topic/{said}")

            # After subscribe, the library's con_up_listener triggers fetch_data().
            # For TS devices that won't work via REST, so we just wait for WS messages.
            print(f"\nWaiting for appliance data (5 min)...")
            end_time = time.time() + 300
            while time.time() < end_time:
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=5)
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = msg.data
                        if data.strip() == "":
                            print(".", end="", flush=True)
                            continue
                        match = DATA_RE.findall(data)
                        if match:
                            print(f"\n  DATA: {{{match[0][:1500]}}}")
                        else:
                            print(f"\n  MSG: {data[:500]}")
                    elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.CLOSED):
                        print(f"\n  WS closed: {msg}")
                        break
                except asyncio.TimeoutError:
                    print(".", end="", flush=True)

            print("\nDone")

if __name__ == "__main__":
    asyncio.run(main())
