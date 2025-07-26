from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/documents.readonly']
SERVICE_ACCOUNT_FILE = 'service_account.json'

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
docs_service = build('docs', 'v1', credentials=credentials)

def extract_text_from_doc(doc_id):
    doc = docs_service.documents().get(documentId=doc_id).execute()
    text = ""
    for element in doc.get("body").get("content"):
        paragraph = element.get("paragraph")
        if paragraph:
            for elem in paragraph.get("elements"):
                text_run = elem.get("textRun")
                if text_run:
                    text += text_run.get("content")
    return text.strip()