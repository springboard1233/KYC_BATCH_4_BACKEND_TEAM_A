from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from pymongo import MongoClient
import pytesseract
from PIL import Image
import re
import io
import time

app = FastAPI()

# ---- MongoDB Connection ----
client = MongoClient("mongodb://localhost:27017/")
db = client["kyc_database"]
users_collection = db["users"]
documents_collection = db["uploaded_documents"]
kyc_data_collection = db["kyc_data"]

# ---- Optional (Windows) Tesseract Path ----
# Uncomment if Tesseract is not in PATH:
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


# ---- Helper: Clean and Parse Text ----
def parse_text(text: str):
    parsed = {
        "panNumber": None,
        "aadhaarNumber": None,
        "name": None,
        "fatherName": None,
        "dob": None,
        "gender": None,
        "address": None,
    }

    # Clean up text
    text = text.replace("PERMANENT ACCOUNT NUMBER", "").replace("INCOME TAX DEPARTMENT", "")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    full_text = "\n".join(lines)

    # --- Aadhaar Number ---
    aadhaar_match = re.search(r"\b\d{4}\s\d{4}\s\d{4}\b", full_text)
    if aadhaar_match:
        parsed["aadhaarNumber"] = aadhaar_match.group().replace(" ", "")

    # --- PAN Number ---
    pan_match = re.search(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", full_text)
    if pan_match:
        parsed["panNumber"] = pan_match.group()

    # --- Name ---
    name_match = re.search(
        r"(?i)name[:\-]?\s*([A-Za-z\s]+?)(?=\s*(father|dob|date|gender|address|photo|signature|$))",
        full_text
    )
    if name_match:
        parsed["name"] = name_match.group(1).strip()
    else:
        alt_name = re.search(r"(?i)(?:name\s)?([A-Z][a-z]+\s[A-Z][a-z]+)", full_text)
        if alt_name:
            parsed["name"] = alt_name.group(1).strip()

    # --- Father's Name (improved) ---
    father_match = re.search(
        r"(?i)father'?s name[:\-]?\s*([A-Za-z\s]+?)(?=\s*(dob|date|gender|address|photo|signature|$))",
        full_text
    )
    if father_match:
        parsed["fatherName"] = father_match.group(1).strip()

    # --- DOB ---
    dob_match = re.search(r"(\d{2,4}[-/]\d{2}[-/]\d{2,4})", full_text)
    if dob_match:
        parsed["dob"] = dob_match.group(1)

    # --- Gender ---
    gender_match = re.search(r"(?i)\b(male|female|transgender)\b", full_text)
    if gender_match:
        parsed["gender"] = gender_match.group(1).capitalize()

    # --- Address (for Aadhaar only) ---
    address = None
    for i, line in enumerate(lines):
        if re.search(r"(?i)^address[:\-]?", line):
            address = line.split(":", 1)[-1].strip()
            break

    # If not found, try line before Aadhaar number
    if not address and parsed["aadhaarNumber"]:
        aadhaar_line_index = next(
            (i for i, l in enumerate(lines) if parsed["aadhaarNumber"][:4] in l.replace(" ", "")),
            None
        )
        if aadhaar_line_index and aadhaar_line_index > 0:
            address = lines[aadhaar_line_index - 1]

    parsed["address"] = address
    return parsed


# ---- OCR + Classification Endpoint ----
@app.post("/upload/")
async def upload_image(file: UploadFile = File(...)):
    try:
        start_time = time.time()
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))

        # OCR Extraction
        text = pytesseract.image_to_string(image)
        parsed = parse_text(text)

        # --- Detect Document Type ---
        if parsed["aadhaarNumber"]:
            doc_type = "Aadhaar"
        elif parsed["panNumber"]:
            doc_type = "PAN"
        else:
            doc_type = "UNKNOWN"

        # Prepare record
        record = {
            "filename": file.filename,
            "docType": doc_type,
            "rawText": text,
            "parsed": parsed,
            "processingTimeMs": int((time.time() - start_time) * 1000)
        }

        # Save to MongoDB
        record_id = documents_collection.insert_one(record).inserted_id
        record["_id"] = str(record_id)

        return JSONResponse(content=record)

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ---- Root Endpoint ----
@app.get("/")
def home():
    return {"message": "KYC OCR API is running successfully!"}
