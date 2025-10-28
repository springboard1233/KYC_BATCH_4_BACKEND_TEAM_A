import re
import pytesseract
from PIL import Image
from .config import TESSERACT_CMD
from concurrent.futures import ThreadPoolExecutor

if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

_executor = ThreadPoolExecutor(max_workers=2)

def run_ocr_sync(path):
    img = Image.open(path)
    text = pytesseract.image_to_string(img, lang='eng')
    return text

async def run_ocr(path):
    # Run blocking OCR in threadpool
    loop = __import__("asyncio").get_event_loop()
    return await loop.run_in_executor(_executor, run_ocr_sync, path)

def parse_kyc(text):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    joined = " ".join(lines)

    # PAN: pattern 5 letters 4 digits 1 letter
    pan_match = re.search(r'\b([A-Z]{5}[0-9]{4}[A-Z])\b', joined, re.IGNORECASE)
    pan = pan_match.group(1).upper() if pan_match else None

    # Aadhaar: 12 digits (allow spaces)
    aadhaar_match = re.search(r'\b(\d{4}\s?\d{4}\s?\d{4})\b', joined)
    if aadhaar_match:
        aadhaar = re.sub(r'\s+', '', aadhaar_match.group(1))
    else:
        aadhaar = None

    # DOB: dd/mm/yyyy or yyyy-mm-dd
    dob_match = re.search(r'\b(\d{2}/\d{2}/\d{4})\b', joined) or re.search(r'\b(\d{4}-\d{2}-\d{2})\b', joined)
    dob = dob_match.group(1) if dob_match else None

    # Gender
    gender = None
    g = re.search(r'\b(Male|Female|MALE|FEMALE|M|F)\b', joined)
    if g:
        gender = g.group(1)

    # Name heuristics: look for lines with uppercase names near PAN or at top
    name = None
    father_name = None
    # If PAN present, often name is on line above PAN or prominent in lines
    if pan:
        for i, ln in enumerate(lines):
            if pan in ln.replace(" ", ""):
                if i > 0:
                    name = lines[i-1]
                break
    if not name and lines:
        name = lines[0]

    # Address heuristic: capture lines after 'Address' keyword
    address = None
    for i, ln in enumerate(lines):
        if ln.lower().startswith("address") or "address" in ln.lower():
            address = " ".join(lines[i+1:i+5])
            break

    parsed = {
        "panNumber": pan,
        "aadhaarNumber": aadhaar,
        "name": name,
        "fatherName": father_name,
        "dob": dob,
        "gender": gender,
        "address": address
    }

    return parsed
