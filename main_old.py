from fastapi import FastAPI, UploadFile, File
from ocr.upload_receipt import upload_receipt_to_drive
from ocr.extract_text import extract_text_from_doc
import uuid

app = FastAPI()

@app.post("/upload-receipt")
async def upload_receipt(file: UploadFile = File(...)):
    # Upload to Drive and convert to Google Doc
    doc_id = await upload_receipt_to_drive(file)

    # Extract text from the Google Doc
    text = extract_text_from_doc(doc_id)

    return {"doc_id": doc_id, "text": text}
