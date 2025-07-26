# ocr/upload_receipt.py
import io
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SCOPES = ['https://www.googleapis.com/auth/drive.file']
flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
creds = flow.run_local_server(port=0)
drive_service = build('drive', 'v3', credentials=creds)

async def upload_receipt_to_drive(file):
    # Read file content into memory
    content = await file.read()
    stream = io.BytesIO(content)

    file_metadata = {
        'name': file.filename,
        'mimeType': 'application/vnd.google-apps.document'
    }

    # Use MediaIoBaseUpload instead of MediaFileUpload
    media = MediaIoBaseUpload(stream, mimetype='image/jpeg')

    uploaded_file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    return uploaded_file.get('id')
