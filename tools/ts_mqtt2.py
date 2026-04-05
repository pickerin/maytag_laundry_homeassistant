"""Connect to Whirlpool AWS IoT via MQTT using awscrt."""
import asyncio
import base64
import json
import os
import uuid
import sys
import aiohttp

from awscrt import mqtt, auth as awsauth, http, io
from awsiot import mqtt_connection_builder

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
        auth_obj = Auth(backend, EMAIL, PASSWORD, session)
        ok = await auth_obj.do_auth(store=False)
        if not ok:
            raise RuntimeError("OAuth failed")

        token = auth_obj.get_access_token()
        payload = token.split(".")[1]
        payload += "=" * (4 - len(payload) % 4)
        jwt_data = json.loads(base64.b64decode(payload))
        ts_saids = jwt_data.get("TS_SAID", [])

        headers = auth_obj.create_headers()
        async with session.get(f"{backend.base_url}/api/v1/cognito/identityid", headers=headers) as r:
            cognito_data = await r.json()

        identity_id = cognito_data["identityId"]
        cognito_token = cognito_data["token"]

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


def main():
    print("Getting AWS credentials...")
    creds = asyncio.run(get_credentials())
    identity_id = creds["identity_id"]
    ts_saids = creds["ts_saids"]
    print(f"Identity ID: {identity_id}")
    print(f"TS SAIDs: {ts_saids}")

    # Set up AWS credentials provider
    credentials_provider = awsauth.AwsCredentialsProvider.new_static(
        access_key_id=creds["access_key"],
        secret_access_key=creds["secret_key"],
        session_token=creds["session_token"],
    )

    received_messages = []
    received_event = asyncio.Event()

    def on_message(topic, payload, dup, qos, retain, **kwargs):
        msg = payload.decode("utf-8", errors="replace")
        print(f"\n  TOPIC: {topic}")
        print(f"  PAYLOAD: {msg[:3000]}")
        received_messages.append((topic, msg))

    # Build MQTT connection with websocket + SigV4
    client_id = f"python-{uuid.uuid4().hex[:8]}"
    print(f"\nConnecting as {client_id} to {IOT_ENDPOINT}...")

    mqtt_connection = mqtt_connection_builder.websockets_with_default_aws_signing(
        endpoint=IOT_ENDPOINT,
        region=AWS_REGION,
        credentials_provider=credentials_provider,
        client_id=client_id,
        on_connection_interrupted=lambda connection, error, **kwargs: print(f"\nConnection interrupted: {error}"),
        on_connection_resumed=lambda connection, return_code, session_present, **kwargs: print(f"\nConnection resumed: {return_code}"),
    )

    connect_future = mqtt_connection.connect()
    connect_future.result(timeout=15)
    print("MQTT Connected!")

    import time as _time

    # Device models from describe_thing thingTypeName
    device_models = {
        "WPR4BV39NFM8D": "MTW7205RR0",  # Washer
        "WPR4VYY9JV8E7": "MGD7205RR0",  # Dryer
    }

    # Subscribe to state updates and command responses with correct model
    for said in ts_saids:
        model = device_models.get(said, "+")
        topics = [
            f"dt/{model}/{said}/state/update",
            f"cmd/{model}/{said}/response/{identity_id}",
        ]
        for topic in topics:
            try:
                subscribe_future, _ = mqtt_connection.subscribe(
                    topic=topic,
                    qos=mqtt.QoS.AT_LEAST_ONCE,
                    callback=on_message,
                )
                subscribe_future.result(timeout=10)
                print(f"  Subscribed: {topic}")
                _time.sleep(0.5)
            except Exception as e:
                print(f"  Sub failed ({topic}): {type(e).__name__}: {e}")

    # Now try publishing getState with the correct model prefix
    for said in ts_saids:
        model = device_models.get(said)
        if not model:
            continue
        try:
            cmd_payload = json.dumps({
                "requestId": str(uuid.uuid4()),
                "timestamp": int(_time.time() * 1000),
                "payload": {"addressee": "appliance", "command": "getState"}
            })
            cmd_topic = f"cmd/{model}/{said}/request/{identity_id}"
            print(f"\n  Publishing getState to {cmd_topic}")
            publish_future, _ = mqtt_connection.publish(
                topic=cmd_topic,
                payload=cmd_payload,
                qos=mqtt.QoS.AT_LEAST_ONCE,
            )
            publish_future.result(timeout=10)
            print(f"  Published OK!")
            _time.sleep(1)
        except Exception as e:
            print(f"  Publish failed: {type(e).__name__}: {e}")

    # Wait for messages
    import time
    print("\nWaiting 60 seconds for messages (appliances should be running)...")
    time.sleep(60)

    print(f"\nTotal messages received: {len(received_messages)}")

    # Disconnect
    disconnect_future = mqtt_connection.disconnect()
    disconnect_future.result(timeout=10)
    print("Disconnected.")


if __name__ == "__main__":
    main()
