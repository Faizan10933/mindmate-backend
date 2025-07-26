# ocr/gemini_parser.py
import os
import json
import re
import google.generativeai as genai

GOOGLE_API_KEY = "AIzaSyA8HGldCViU0bKIdo7EtfH7D-HdkvFRKaw"
genai.configure(api_key=GOOGLE_API_KEY)

model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest")

def extract_structured_receipt(text: str) -> dict:
    prompt = f"""
You are a receipt parsing assistant. Extract structured JSON from the following receipt text.

If any fields are missing, skip them. Return output in this JSON format:

{{
  "restaurant": "",
  "location": "",
  "order_number": "",
  "items": [],
  "subtotal": "",
  "vat": "",
  "total": "",
  "payment_method": "",
  "served_by": "",
  "timestamp": ""
}}

Receipt Text:
{text}
"""
    try:
        response = model.generate_content(prompt)
        content = response.text.strip()

        content = re.sub(r"^```json|```$", "", content.strip(), flags=re.MULTILINE).strip("` \n")
        return json.loads(content)
    except Exception as e:
        return {"error": str(e), "raw_response": response.text if 'response' in locals() else None}

def generate_summary_from_receipts(text_blob: str) -> dict:
    prompt = f"""
You are an assistant for expense insights.

Here are multiple receipts parsed from a user's purchase history. Analyze the data and return a **JSON** object with the following fields:

- total_amount_spent: float (e.g. 238.75)
- top_restaurants: list of dicts with keys: name (string), visits (int)
- frequently_purchased_items: dict where keys are restaurant names, values are list of item names
- patterns: list of dicts with keys: type (string), description (string)
- recommendations: list of strings

Return only a valid JSON object. Do not include any explanation or text before or after the JSON.

Receipts:
{text_blob}
"""

    try:
        response = model.generate_content(prompt)
        raw_output = response.text.strip()

        if raw_output.startswith("```json"):
            raw_output = raw_output[7:].strip()
        if raw_output.startswith("```"):
            raw_output = raw_output[3:].strip()
        if raw_output.endswith("```"):
            raw_output = raw_output[:-3].strip()

        return json.loads(raw_output)

    except json.JSONDecodeError as json_err:
        return {
            "summary": {
                "error": "Failed to parse JSON",
                "details": str(json_err),
                "raw_output": response.text
            }
        }
    except Exception as e:
        return {
            "summary": {
                "error": "Unhandled exception",
                "details": str(e)
            }
        }

def answer_user_query_over_receipts(receipts_blob: str, user_query: str) -> str:
    prompt = f"""
You are an intelligent assistant that helps users understand their purchase history.

Below are receipts:
{receipts_blob}

User's question:
{user_query}

Provide a clear and helpful answer based only on the receipt data.
"""
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Error: {e}"
