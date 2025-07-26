import aiofiles
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = 'service_account.json'

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=credentials)

async def upload_receipt_to_drive(file):
    import tempfile
    import os

    temp_dir = tempfile.gettempdir()
    temp_file_path = os.path.join(temp_dir, file.filename)
    async with aiofiles.open(temp_file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)

    file_metadata = {
    'name': file.filename,
    'parents': ['1lztXSaK0QWcrbqHk83cnhVplQ3xh7TPI'],  # replace this
    'mimeType': 'application/vnd.google-apps.document'
}

    media = MediaFileUpload(temp_file_path, mimetype='image/jpeg')
    uploaded_file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    os.remove(temp_file_path)
    return uploaded_file.get('id')