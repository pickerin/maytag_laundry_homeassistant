"""Connect to Whirlpool AWS IoT via MQTT and get appliance state."""
import asyncio
import base64
import json
import os
import uuid
import time
import aiohttp
import paho.mqtt.client as mqtt
from urllib.parse import quote

from whirlpool.auth import Auth
from whirlpool.backendselector import BackendSelector, Brand, Region

EMAIL = os.environ["WHIRLPOOL_EMAIL"]
PASSWORD = os.environ["WHIRLPOOL_PASSWORD"]
IOT_ENDPOINT = "wt.applianceconnect.net"
AWS_REGION = "us-east-2"


async def get_credentials():
    """Get AWS temporary credentials via OAuth -> Cognito chain."""
    backend = BackendSelector(Brand.Maytag, Region.US)
    async with aiohttp.ClientSession() as session:
        auth = Auth(backend, EMAIL, PASSWORD, session)
        ok = await auth.do_auth(store=False)
        if not ok:
            raise RuntimeError("OAuth failed")

        # Decode JWT for TS_SAID
        token = auth.get_access_token()
        payload = token.split(".")[1]
        payload += "=" * (4 - len(payload) % 4)
        jwt_data = json.loads(base64.b64decode(payload))
        ts_saids = jwt_data.get("TS_SAID", [])

        # Get Cognito identity
        headers = auth.create_headers()
        async with session.get(f"{backend.base_url}/api/v1/cognito/identityid", headers=headers) as r:
            cognito_data = await r.json()

        identity_id = cognito_data["identityId"]
        cognito_token = cognito_data["token"]

        # Exchange for AWS credentials
        async with session.post(
            f"https://cognito-identity.{AWS_REGION}.amazonaws.com/",
            headers={
                "Content-Type": "application/x-amz-json-1.1",
                "X-Amz-Target": "AWSCognitoIdentityService.GetCredentialsForIdentity",
            },
            json={
                "IdentityId": identity_id,
                "Logins": {"cognito-identity.amazonaws.com": cognito_token},
            },
        ) as r:
            creds = await r.json(content_type=None)

        credentials = creds["Credentials"]
        return {
            "access_key": credentials["AccessKeyId"],
            "secret_key": credentials["SecretKey"],
            "session_token": credentials["SessionToken"],
            "identity_id": identity_id,
            "ts_saids": ts_saids,
        }


def sign_mqtt_url(endpoint, region, access_key, secret_key, session_token):
    """Create a SigV4 signed WebSocket URL for AWS IoT MQTT."""
    import hmac
    import hashlib
    import datetime

    method = "GET"
    service = "iotdevicegateway"
    host = endpoint
    uri = "/mqtt"

    t = datetime.datetime.utcnow()
    datestamp = t.strftime("%Y%m%d")
    amzdate = t.strftime("%Y%m%dT%H%M%SZ")

    credential_scope = f"{datestamp}/{region}/{service}/aws4_request"
    canonical_querystring = (
        f"X-Amz-Algorithm=AWS4-HMAC-SHA256"
        f"&X-Amz-Credential={quote(access_key + '/' + credential_scope, safe='')}"
        f"&X-Amz-Date={amzdate}"
        f"&X-Amz-Expires=86400"
        f"&X-Amz-Security-Token={quote(session_token, safe='')}"
        f"&X-Amz-SignedHeaders=host"
    )

    canonical_headers = f"host:{host}\n"
    payload_hash = hashlib.sha256(b"").hexdigest()
    canonical_request = f"{method}\n{uri}\n{canonical_querystring}\n{canonical_headers}\nhost\n{payload_hash}"

    string_to_sign = f"AWS4-HMAC-SHA256\n{amzdate}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode()).hexdigest()}"

    def sign(key, msg):
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    signing_key = sign(
        sign(sign(sign(f"AWS4{secret_key}".encode("utf-8"), datestamp), region), service),
        "aws4_request",
    )
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    return f"wss://{host}{uri}?{canonical_querystring}&X-Amz-Signature={signature}"


def main():
    print("Getting AWS credentials...")
    creds = asyncio.run(get_credentials())
    print(f"Identity ID: {creds['identity_id']}")
    print(f"TS SAIDs: {creds['ts_saids']}")

    ws_url = sign_mqtt_url(
        IOT_ENDPOINT, AWS_REGION,
        creds["access_key"], creds["secret_key"], creds["session_token"],
    )
    print(f"\nSigned MQTT WebSocket URL (first 100): {ws_url[:100]}...")

    received = []

    def on_connect(client, userdata, flags, rc, properties=None):
        print(f"\nMQTT Connected! rc={rc}")
        if rc != 0:
            print(f"Connection failed with code {rc}")
            return

        # Subscribe to state updates and shadow for each SAID
        for said in creds["ts_saids"]:
            topics = [
                f"$aws/things/{said}/shadow/get/accepted",
                f"$aws/things/{said}/shadow/get/rejected",
                f"$aws/things/{said}/shadow/update/accepted",
                f"dt/+/{said}/state/update",
                f"cmd/+/{said}/response/{creds['identity_id']}",
                f"$aws/events/presence/connected/{said}",
                f"$aws/events/presence/disconnected/{said}",
            ]
            for topic in topics:
                client.subscribe(topic, qos=1)
                print(f"  Subscribed: {topic}")

            # Request shadow
            print(f"\n  Requesting shadow for {said}...")
            client.publish(f"$aws/things/{said}/shadow/get", "", qos=1)

    def on_message(client, userdata, msg):
        payload = msg.payload.decode("utf-8", errors="replace")
        print(f"\n  TOPIC: {msg.topic}")
        print(f"  PAYLOAD: {payload[:2000]}")
        received.append((msg.topic, payload))

    def on_disconnect(client, userdata, rc, properties=None, reason_code=None):
        print(f"\nDisconnected: rc={rc}")

    client = mqtt.Client(
        client_id=f"python-{uuid.uuid4().hex[:8]}",
        transport="websockets",
        protocol=mqtt.MQTTv311,
    )
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    client.tls_set()

    # Parse the signed URL for connection
    import ssl
    client.ws_set_options(path=ws_url.split(IOT_ENDPOINT)[1])

    print(f"\nConnecting to {IOT_ENDPOINT}:443 via MQTT over WebSocket...")
    try:
        client.connect(IOT_ENDPOINT, 443, keepalive=30)
        client.loop_start()
        print("Waiting 30 seconds for messages...")
        time.sleep(30)
        client.loop_stop()
        client.disconnect()
    except Exception as e:
        print(f"Connection error: {type(e).__name__}: {e}")

    print(f"\nTotal messages received: {len(received)}")


if __name__ == "__main__":
    main()
