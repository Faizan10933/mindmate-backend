from fastapi import FastAPI, UploadFile, File, Body
from ocr.upload_receipt import upload_receipt_to_drive
from ocr.extract_text import extract_text_from_doc
from ocr.gemini_parser import extract_structured_receipt, generate_summary_from_receipts, answer_user_query_over_receipts
from ocr.firestore_client import save_receipt_to_firestore, get_all_receipts, get_all_receipt_texts
from analyze_data import Data_Processor
from pydantic import BaseModel
import pandas as pd

# Pydantic model for input validation
class TransactionInput(BaseModel):
    merchant: str
    merchant_category: str
    amount: float
    timestamp: str


app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or restrict to ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/upload-receipt")
async def upload_receipt(file: UploadFile = File(...)):
    doc_id = await upload_receipt_to_drive(file)
    text = extract_text_from_doc(doc_id)
    parsed = extract_structured_receipt(text)
    save_receipt_to_firestore(doc_id, text, parsed)
    return {"doc_id": doc_id, "text": text, "parsed": parsed}

@app.get("/receipts")
def list_receipts():
    return get_all_receipts()

@app.get("/summary")
def summary():
    all_text = get_all_receipt_texts()
    summary = generate_summary_from_receipts(all_text)
    return {"summary": summary}

@app.post("/ask")
def ask_receipt_question(question: str = Body(..., embed=True)):
    all_text = get_all_receipt_texts()
    answer = answer_user_query_over_receipts(question, all_text)
    return {"question": question, "answer": answer}


from ocr.gemini_parser import detect_impulsive_behavior

@app.get("/impulse-check")
def impulse_alerts():
    receipts = get_all_receipts()
    analysis = detect_impulsive_behavior(receipts)
    return {"impulse_analysis": analysis}

@app.post("/analyze-transaction/", response_model=dict)
async def analyze_transaction(transaction: TransactionInput):
    try:
        # Fetch data from Firestore
        receipts = get_all_receipts()
        
        # Initialize Data_Processor
        processor = Data_Processor(receipts)
        
        # Process the input JSON
        input_data = transaction.dict()
        result = processor.calculate_stats(input_data)
        
        # Format the response
        z_scores, (freq_flag, freq_stats) = result
        response = {
            "z_scores": {
                "rolling_amount": {"z_score": float(z_scores[0][0]), "stats": z_scores[0][1]},
                "bin_hour_amount": {"z_score": float(z_scores[1][0]), "stats": z_scores[1][1]},
                "merchant_cat_amount": {"z_score": float(z_scores[2][0]), "stats": z_scores[2][1]},
                "merchant_amount": {"z_score": float(z_scores[3][0]), "stats": z_scores[3][1]},
            },
            "high_freq_low_volume": {
                "flag": bool(freq_flag),
                "stats": freq_stats
            }
        }
        return response
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

import json
import uuid

@app.post("/insert")
def insert_receipts():
    try:
        with open("transactions_modified.json", "r") as f:
            data = json.load(f)

        for receipt in data:
            doc_id = str(uuid.uuid4())  # Unique ID
            save_receipt_to_firestore(doc_id, receipt)

        return {"status": "success", "inserted": len(data)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# @app.post("/insert")
# def insert_receipts():
#     save_receipt_to_firestore(
#     doc_id="dominos_01",
#     text="...",
#     parsed={
#         "restaurant": "Domino's Pizza",
#         "location": "MG Road",
#         "order_number": "12",
#         "items": [
#             {"item": "Margherita Pizza", "price": "8.99"},
#             {"item": "Garlic Bread", "price": "3.49"},
#             {"item": "Choco Lava Cake", "price": "2.99"}
#         ],
#         "subtotal": "15.47",
#         "total": "17.00",
#         "payment_method": "UPI",
#         "served_by": "ARUN",
#         "timestamp": "2024-07-01 19:45"
#     }
#     )
    
#     save_receipt_to_firestore(
#     doc_id="starbucks_01",
#     text="...",
#     parsed={
#         "restaurant": "Starbucks",
#         "location": "Indiranagar",
#         "order_number": "31",
#         "items": [
#             {"item": "Caffe Latte", "price": "4.50"},
#             {"item": "Espresso", "price": "3.00"}
#         ],
#         "subtotal": "7.50",
#         "total": "8.25",
#         "payment_method": "Credit Card",
#         "served_by": "PRIYA",
#         "timestamp": "2024-06-20 09:15"
#     }
#     )


#     save_receipt_to_firestore(
#     doc_id="subway_01",
#     text="...",
#     parsed={
#         "restaurant": "Subway",
#         "location": "BTM Layout",
#         "order_number": "18",
#         "items": [
#             {"item": "Veggie Delight", "price": "6.00"},
#             {"item": "Pepsi", "price": "1.50"}
#         ],
#         "subtotal": "7.50",
#         "total": "8.00",
#         "payment_method": "Cash",
#         "served_by": "RAHUL",
#         "timestamp": "2024-06-15 13:22"
#     }
#     )


#     save_receipt_to_firestore(
#     doc_id="mcd_01",
#     text="...",
#     parsed={
#         "restaurant": "McDonald's",
#         "location": "Brigade Road",
#         "order_number": "22",
#         "items": [
#             {"item": "McChicken", "price": "4.00"},
#             {"item": "French Fries", "price": "2.00"},
#             {"item": "Coke", "price": "1.50"}
#         ],
#         "subtotal": "7.50",
#         "total": "7.50",
#         "payment_method": "Credit Card",
#         "served_by": "RITA",
#         "timestamp": "2024-06-10 17:10"
#     }
#     )

    
