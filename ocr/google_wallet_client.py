# ocr/google_wallet_client.py

import json
import uuid
import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from ocr.wallet_config import WALLET_ISSUER_ID, CLASS_ID, SERVICE_ACCOUNT_FILE

SCOPES = ['https://www.googleapis.com/auth/wallet_object.issuer']

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)

def create_wallet_receipt(user_id: str, receipt_data: dict):
    object_id = f"{WALLET_ISSUER_ID}.{user_id}-{uuid.uuid4().hex[:8]}"

    object_payload = {
        "id": object_id,
        "classId": CLASS_ID,
        "heroImage": {
            "sourceUri": {"uri": "https://yourdomain.com/logo.png"},  # Optional
            "contentDescription": {"defaultValue": {"language": "en-US", "value": "Receipt"}}
        },
        "textModulesData": [
            {
                "header": "Spending Summary",
                "body": json.dumps(receipt_data, indent=2)[:500]  # Truncate if too long
            }
        ],
        "barcode": {
            "type": "QR_CODE",
            "value": object_id
        },
        "state": "ACTIVE"
    }

    credentials.refresh(Request())

    response = requests.post(
        'https://walletobjects.googleapis.com/walletobjects/v1/genericObject',
        headers={
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/json"
        },
        data=json.dumps(object_payload)
    )

    if response.status_code >= 200 and response.status_code < 300:
        return response.json()
    else:
        print("Error pushing pass:", response.text)
        return {"error": response.text}
