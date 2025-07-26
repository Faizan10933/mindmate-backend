from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/documents.readonly']
flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
creds = flow.run_local_server(port=0)
docs_service = build('docs', 'v1', credentials=creds)

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