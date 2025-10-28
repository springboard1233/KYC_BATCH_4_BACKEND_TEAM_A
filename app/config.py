import os

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "kyc_db")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
# Ensure TESSERACT_CMD can be set if tesseract binary not on PATH
TESSERACT_CMD = os.getenv("TESSERACT_CMD", None)

# Ensure UPLOAD_DIR is an absolute path and exists
UPLOAD_DIR = os.path.abspath(UPLOAD_DIR)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Try to auto-detect tesseract binary if env var not provided
import shutil

if not TESSERACT_CMD:
    # prefer system PATH
    found = shutil.which("tesseract")
    if found:
        TESSERACT_CMD = found
    else:
        # common Windows install locations
        win_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
        ]
        for p in win_paths:
            if os.path.exists(p):
                TESSERACT_CMD = p
                break
# If still None, instruct user to set env var (no runtime side effects here)
