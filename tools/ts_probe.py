"""Probe the TS appliance AWS IoT path: OAuth -> Cognito -> MQTT."""
import asyncio
import base64
import json
import aiohttp

from whirlpool.auth import Auth
from whirlpool.backendselector import BackendSelector, Brand, Region

EMAIL = "REDACTED_EMAIL@example.com"
PASSWORD = "REDACTED_PASSWORD"

async def main():
    backend = BackendSelector(Brand.Maytag, Region.US)
    async with aiohttp.ClientSession() as session:
        # Step 1: OAuth login
        auth = Auth(backend, EMAIL, PASSWORD, session)
        ok = await auth.do_auth(store=False)
        print(f"1. OAuth: {'OK' if ok else 'FAILED'}")
        if not ok:
            return

        # Decode JWT to get TS_SAID
        token = auth.get_access_token()
        payload = token.split(".")[1]
        payload += "=" * (4 - len(payload) % 4)
        jwt_data = json.loads(base64.b64decode(payload))
        ts_saids = jwt_data.get("TS_SAID", [])
        print(f"   TS_SAID: {ts_saids}")

        # Step 2: Get Cognito identity
        headers = auth.create_headers()
        print(f"\n2. Getting Cognito identity from /api/v1/cognito/identityid")
        async with session.get(
            f"{backend.base_url}/api/v1/cognito/identityid",
            headers=headers,
        ) as r:
            print(f"   Status: {r.status}")
            body = await r.text()
            print(f"   Body: {body[:2000]}")

            if r.status == 200:
                cognito_data = json.loads(body)
                identity_id = cognito_data.get("identityId", "")
                cognito_token = cognito_data.get("token", "")
                print(f"   Identity ID: {identity_id}")
                print(f"   Token (first 50): {cognito_token[:50]}...")

                # Step 3: Exchange for AWS credentials via Cognito
                print(f"\n3. Getting AWS credentials via Cognito GetCredentialsForIdentity")
                cognito_url = "https://cognito-identity.us-east-2.amazonaws.com/"
                cognito_headers = {
                    "Content-Type": "application/x-amz-json-1.1",
                    "X-Amz-Target": "AWSCognitoIdentityService.GetCredentialsForIdentity",
                }
                cognito_body = {
                    "IdentityId": identity_id,
                    "Logins": {
                        "cognito-identity.amazonaws.com": cognito_token,
                    },
                }
                async with session.post(
                    cognito_url,
                    headers=cognito_headers,
                    json=cognito_body,
                ) as cr:
                    print(f"   Status: {cr.status}")
                    cred_body = await cr.text()
                    print(f"   Body: {cred_body[:2000]}")

                    if cr.status == 200:
                        creds = json.loads(cred_body)
                        credentials = creds.get("Credentials", {})
                        access_key = credentials.get("AccessKeyId", "")
                        secret_key = credentials.get("SecretKey", "")
                        session_token = credentials.get("SessionToken", "")
                        print(f"\n   AWS Access Key: {access_key[:20]}...")
                        print(f"   AWS Secret Key: {secret_key[:20]}...")
                        print(f"   Expiration: {credentials.get('Expiration', '')}")

                        # Step 4: Get IoT endpoint using AWS credentials
                        print(f"\n4. Getting IoT endpoint via DescribeEndpoint")
                        import boto3
                        iot_client = boto3.client(
                            "iot",
                            region_name="us-east-2",
                            aws_access_key_id=access_key,
                            aws_secret_access_key=secret_key,
                            aws_session_token=session_token,
                        )
                        iot_endpoint = "wt.applianceconnect.net"
                        print(f"   IoT Endpoint: {iot_endpoint}")

                        # Step 5: Get thing shadows via REST
                        print(f"\n5. Fetching thing shadows")
                        iot_data = boto3.client(
                            "iot-data",
                            region_name="us-east-2",
                            aws_access_key_id=access_key,
                            aws_secret_access_key=secret_key,
                            aws_session_token=session_token,
                            endpoint_url=f"https://{iot_endpoint}",
                        )
                        for said in ts_saids:
                            print(f"\n   Getting shadow for {said}:")
                            try:
                                shadow = iot_data.get_thing_shadow(thingName=said)
                                shadow_body = shadow["payload"].read().decode()
                                parsed = json.loads(shadow_body)
                                print(f"   Shadow: {json.dumps(parsed, indent=2)[:3000]}")
                            except Exception as e:
                                print(f"   Error: {type(e).__name__}: {str(e)[:300]}")

if __name__ == "__main__":
    asyncio.run(main())
