# ocr/firestore_client.py
from google.cloud import firestore
import os
from datetime import datetime


# Set this once using your service account
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "firestore-credentials.json"

db = firestore.Client()
receipts_collection = db.collection("receipts_synthetic10001234")

# def save_receipt_to_firestore(doc_id, text, parsed):
#     data = {
#         "doc_id": doc_id,
#         "text": text,
#         "parsed": parsed,
#         "created_at": datetime.utcnow().isoformat()

#     }
#     receipts_collection.document(doc_id).set(data)

def save_receipt_to_firestore(doc_id, data):
    data["doc_id"] = doc_id
    data["created_at"] = datetime.utcnow().isoformat()
    receipts_collection.document(doc_id).set(data)

def get_all_receipts():
    try:
        print("🔍 Fetching receipts from Firestore...")
        receipts_ref = db.collection("receipts_synthetic10001234")
        docs = receipts_ref.stream()  # <-- likely blocking here
        results = [doc.to_dict() for doc in docs]
        print(f"✅ Retrieved {len(results)} receipts")
        return results
    except Exception as e:
        print(f"❌ Firestore error: {e}")
        return {"error": str(e)}


import json

def get_all_receipt_texts():
    docs = receipts_collection.stream()
    all_texts = []
    for doc in docs:
        data = doc.to_dict()
        try:
            all_texts.append(json.dumps(data, ensure_ascii=False))
        except Exception as e:
            print(f"❌ Skipping invalid doc {doc.id}: {e}")
    return "\n---\n".join(all_texts)

