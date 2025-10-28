# KYC OCR Service (FastAPI + pytesseract + MongoDB)

## Brief

Small FastAPI service that accepts image uploads, runs OCR (pytesseract), extracts basic PAN/Aadhaar fields with regex heuristics, and stores results in MongoDB.

## Status

- Backend: FastAPI (app/main.py)
- OCR: pytesseract (requires system Tesseract)
- DB: MongoDB (default: mongodb://localhost:27017)
- Storage: in-memory/DB (images processed from upload bytes; not saved to filesystem in current main.py)

## Prerequisites

- Python 3.8+
- pip
- MongoDB (local or remote)
- System Tesseract OCR binary installed

## Install Tesseract

- Windows: download & run the installer from https://github.com/tesseract-ocr/tesseract/releases (default path: `C:\Program Files\Tesseract-OCR\tesseract.exe`)
- macOS (Homebrew): `brew install tesseract`
- Debian/Ubuntu: `sudo apt update && sudo apt install -y tesseract-ocr`
- Verify: `tesseract --version`

If Tesseract is not on PATH on Windows, set the TESSERACT_CMD environment variable (examples below).

## Environment variables

- MONGO_URI (default: `mongodb://localhost:27017`)
- DB_NAME (default: `kyc_database`)
- UPLOAD_DIR (not required by current main.py; config.py in project may use it)
- TESSERACT_CMD — full path to tesseract binary if not on PATH
  - Windows PowerShell (persist):
    [Environment]::SetEnvironmentVariable("TESSERACT_CMD","C:\Program Files\Tesseract-OCR\tesseract.exe","User")
  - Windows CMD (persist):
    setx TESSERACT_CMD "C:\Program Files\Tesseract-OCR\tesseract.exe"
  - macOS/Linux (temporary):
    export TESSERACT_CMD=/usr/local/bin/tesseract
  - macOS/Linux (persist): add to `~/.bashrc` or `~/.zshrc`

## Project setup

1. Clone or copy project into your machine (project root here).
2. (Optional) Create and activate a virtual environment:
   - python -m venv .venv
   - Windows: .venv\Scripts\activate
   - macOS/Linux: source .venv/bin/activate
3. Install dependencies:
   - Ensure `requirements.txt` exists (if not, create it with needed packages)
   - pip install -r requirements.txt
     Typical deps: fastapi, uvicorn[standard], python-multipart, pillow, pytesseract, pymongo

## Run the API

Start the server:

- uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

## Endpoints

- GET /

  - Health/info: returns a simple message.

- POST /upload/
  - Accepts: multipart/form-data with field `file` (an image)
  - Returns: JSON record containing:
    - filename
    - docType (Aadhaar | PAN | UNKNOWN)
    - rawText (OCR output)
    - parsed (parsed fields: panNumber, aadhaarNumber, name, fatherName, dob, gender, address)
    - processingTimeMs

## Testing examples

Using curl:

- Linux/macOS:
  curl -X POST "http://localhost:8000/upload/" -F "file=@/path/to/document.jpg"
- Windows (PowerShell):
  curl -X POST "http://localhost:8000/upload/" -F "file=@C:\path\to\document.jpg"

Example response (trimmed):
{
"filename": "document.jpg",
"docType": "PAN",
"rawText": "OCR extracted text ...",
"parsed": {
"panNumber": "ABCDE1234F",
"aadhaarNumber": null,
"name": "John Doe",
"fatherName": null,
"dob": "01/01/1990",
"gender": "Male",
"address": "..."
},
"processingTimeMs": 420
}

## MongoDB storage

Documents are inserted into the `uploaded_documents` collection in the configured database.

- Default connection: `mongodb://localhost:27017/`
- DB name used by main.py: `kyc_database`
- Collections:
  - users
  - uploaded_documents
  - kyc_data

## Troubleshooting

- pytesseract throws "tesseract not found": ensure Tesseract installed and on PATH, or set `TESSERACT_CMD` env var, or uncomment the line in `app/main.py` setting `pytesseract.pytesseract.tesseract_cmd`.
- Mongo connection errors: confirm MongoDB is running and `MONGO_URI` is correct.
- Bad OCR quality: try preprocessing images (increase DPI, convert to grayscale, thresholding) before sending to pytesseract.

## Security & next steps

- Add authentication (JWT) and user association for uploads.
- Persist raw uploaded files to disk or cloud (S3) and store reference in DB.
- Improve parsing using layout-aware OCR (OCR libraries with bounding boxes) and stricter regex or ML-based named-entity extraction.
- Add logging, input validation and rate limiting.
- Add tests and CI.

## License

MIT

## Contact / Notes

- This README reflects the current code in `app/main.py`. If you want a fuller scaffold (config, async Motor client, file-storage, /kyc/{id} retrieval), say which additions to generate next.
