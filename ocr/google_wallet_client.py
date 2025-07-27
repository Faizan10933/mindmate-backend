from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2 import service_account
import jwt
import json
import uuid
import time

# Constants
SERVICE_ACCOUNT_KEY_FILE = 'service_account_key.json'
ISSUER_ID = '3388000000022973933'
SCOPES = ['https://www.googleapis.com/auth/wallet_object.issuer']
CLASS_SUFFIX = 'custom_pass_class'


def get_wallet_service():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_KEY_FILE, scopes=SCOPES
    )
    service = build('walletobjects', 'v1', credentials=credentials)
    return service


def create_generic_class(service, issuer_id, class_suffix):
    class_id = f"{issuer_id}.{class_suffix}"
    try:
        service.genericclass().get(resourceId=class_id).execute()
        return class_id
    except HttpError as e:
        if e.resp.status != 404:
            raise

    new_class = {
        "id": class_id,
        "issuerName": "Your Company",
        "hexBackgroundColor": "#4285F4",
        "textModulesData": [
            {
                "header": "Welcome",
                "body": "This is your personalized digital pass.",
                "id": "welcome"
            }
        ]
    }

    service.genericclass().insert(body=new_class).execute()
    return class_id


def create_generic_object(service, issuer_id, class_suffix, user_name, message):
    object_id_suffix = str(uuid.uuid4())
    object_id = f"{issuer_id}.{object_id_suffix}"
    class_id = f"{issuer_id}.{class_suffix}"

    new_object = {
        "id": object_id,
        "classId": class_id,
        "state": "ACTIVE",
        "cardTitle": {
            "defaultValue": {
                "language": "en-US",
                "value": "Your Digital Pass"
            }
        },
        "header": {
            "defaultValue": {
                "language": "en-US",
                "value": "Digital Membership"
            }
        },
        "textModulesData": [
            {
                "header": "Name",
                "body": user_name,
                "id": "user_name"
            },
            {
                "header": "Message",
                "body": message,
                "id": "custom_message"
            }
        ],
        "barcode": {
            "type": "QR_CODE",
            "value": f"https://example.com/pass/{object_id_suffix}"
        }
    }

    service.genericobject().insert(body=new_object).execute()
    return object_id


def create_jwt_add_to_wallet_url(class_id, object_id):
    with open(SERVICE_ACCOUNT_KEY_FILE, 'r') as f:
        service_account_info = json.load(f)

    payload = {
        "iss": service_account_info['client_email'],
        "aud": "google",
        "typ": "savetowallet",
        "iat": int(time.time()),
        "origins": ["https://yourdomain.com"],
        "payload": {
            "genericObjects": [
                {
                    "id": object_id,
                    "classId": class_id
                }
            ]
        }
    }

    signed_jwt = jwt.encode(
        payload,
        service_account_info['private_key'],
        algorithm='RS256',
        headers={'kid': service_account_info['private_key_id']}
    )

    return f"https://pay.google.com/gp/v/save/{signed_jwt}"


def generate_wallet_pass(user_name: str, message: str) -> str:
    try:
        service = get_wallet_service()
        class_id = create_generic_class(service, ISSUER_ID, CLASS_SUFFIX)
        object_id = create_generic_object(service, ISSUER_ID, CLASS_SUFFIX, user_name, message)
        url = create_jwt_add_to_wallet_url(class_id, object_id)
        return url
    except HttpError as err:
        raise Exception(f"Google Wallet API Error: {err.resp.status} - {err.content}")
    except Exception as e:
        raise Exception(f"Unexpected error: {str(e)}")