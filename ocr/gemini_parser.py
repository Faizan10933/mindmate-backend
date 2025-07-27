# ocr/gemini_parser.py
import os
import json
import re
import google.generativeai as genai

GOOGLE_API_KEY = "AIzaSyCq4k-_rJVMpaF8znEIJNFAsMhJj_3OmNk"
genai.configure(api_key=GOOGLE_API_KEY)

model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest")

def extract_structured_receipt(text: str) -> dict:
    prompt = f"""
You are a receipt parsing assistant. Extract structured JSON from the following receipt text.

If any fields are missing, skip them. Return output in this JSON format:

{{
  "user_id": "",
  "merchant": "",
  "merchant_category": "",
  "amount": 0.0,
  "timestamp": "",
  "parsed": {{
    "items": [
      {{
        "item": "",
        "price": ""
      }}
    ],
    "subtotal": "",
    "order_number": "",
    "payment_method": "",
    "location": "",
  }}
}}

## timestamp value always respon in "%Y-%m-%dT%H:%M:%S.%f" date-time format- example "timestamp": "2025-06-20T23:58:37.567979"
## Convert amount to INR always.
## Try to infer the merchant category through merchant name or line of business, eg. Blue Tokai falls in Coffee Shops category.
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
    

def detect_impulsive_behavior(receipts: list) -> str:
    prompt = f"""
You are a behavioral finance assistant.

The user’s receipts are listed below. Your job is to analyze and detect signs of **impulsive or emotional spending**.

Instructions:
1. Compare older vs newer purchases.
2. Look for spikes in frequency, amount, or categories like coffee, snacks, fast food, treats.
3. Identify patterns like late-night orders or multiple small-value purchases in a short span.
4. Give insights on what may be impulsive behavior.

Respond in JSON format:
- "alerts": List of identified impulsive patterns
- "suggestions": Advice to improve spending habits
- "summary": Optional text explanation

Receipts:
{receipts}
"""
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error: {e}"


def summarize_receipt_for_pass(resp: dict) -> str:
    # reasoning = resp.get("final", {}).get("raw_response", "")
    
    # # Clean out markdown/code block formatting if present
    # reasoning = reasoning.replace("```json", "").replace("```", "").strip()

    prompt = f"""
You are a helpful assistant that generates short wallet pass notifications based on receipt analysis.

Summarize this transaction analysis into 1–2 short friendly lines for a mobile notification.
Avoid technical terms or explanations. Be clear and natural.

Receipt AI Analysis:
{str(resp)}

Summary:
"""

    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return "Transaction saved and analyzed."


