from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pymongo import MongoClient
from passlib.context import CryptContext
import jwt
import pytesseract
from PIL import Image
import io
import re
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

# -------------------- CONFIG --------------------
load_dotenv()  # Load values from .env

app = FastAPI()
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

# MongoDB connection
client = MongoClient("mongodb://localhost:27017/")
db = client["kyc_database"]
users_collection = db["users"]
documents_collection = db["uploaded_documents"]
kyc_data_collection = db["kyc_data"]

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# -------------------- HELPERS --------------------
def is_valid_email(email: str) -> bool:
    """Validate email using regex."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None


def is_valid_password(password: str) -> bool:
    """Check password rules: 8-16 chars, 1 uppercase, 1 lowercase, 1 number, 1 special char."""
    pattern = (
        r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*#?&])[A-Za-z\d@$!#%*?&]{8,16}$"
    )
    return re.match(pattern, password) is not None


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def hash_password(password: str):
    """Hash password safely (trimmed for bcrypt limit)."""
    if len(password) > 72:
        password = password[:72]
    return pwd_context.hash(password)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password[:72], hashed_password)


def get_current_user(token: str = Depends(oauth2_scheme)):
    """Get user details from JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        user = users_collection.find_one({"email": email})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


# -------------------- A. USER AUTH --------------------
@app.post("/signup")
def signup(name: str = Form(...), email: str = Form(...), password: str = Form(...)):
    # Email validation
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    # Password validation
    if not is_valid_password(password):
        raise HTTPException(
            status_code=400,
            detail=(
                "Password must be 8–16 characters long, include at least one uppercase letter, "
                "one lowercase letter, one number, and one special character."
            ),
        )

    # Check for existing email
    if users_collection.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    # Store user
    hashed_pw = hash_password(password)
    users_collection.insert_one(
        {"name": name, "email": email, "password": hashed_pw, "createdAt": datetime.utcnow()}
    )

    return {"message": "Signup successful"}


@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = users_collection.find_one({"email": form_data.username})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email")

    if not verify_password(form_data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Create JWT token
    token = create_access_token({"sub": user["email"]})
    return {"access_token": token, "token_type": "bearer"}


# -------------------- B. OCR TEXT PARSER --------------------
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

    # Clean and split text
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    full_text = "\n".join(lines)

    # Aadhaar
    aadhaar_match = re.search(r"\b\d{4}\s\d{4}\s\d{4}\b", full_text)
    if aadhaar_match:
        parsed["aadhaarNumber"] = aadhaar_match.group().replace(" ", "")

    # PAN
    pan_match = re.search(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", full_text)
    if pan_match:
        parsed["panNumber"] = pan_match.group()

    # Name
    name_match = re.search(
        r"(?i)\bname[:\-]?\s*([A-Za-z\s]+?)(?=\s*(dob|father|date|gender|address|$))", full_text
    )
    if name_match:
        parsed["name"] = name_match.group(1).strip()
    else:
        alt_name = re.search(r"(?i)(?:name\s)?([A-Z][a-z]+\s[A-Z][a-z]+)", full_text)
        if alt_name:
            parsed["name"] = alt_name.group(1).strip()

    # Father Name
    father_match = re.search(r"Father'?s Name[:\-]?\s*([A-Za-z ]+)", full_text, re.IGNORECASE)
    if father_match:
        parsed["fatherName"] = father_match.group(1).strip()

    # DOB
    dob_match = re.search(r"(\d{2,4}[-/]\d{2}[-/]\d{2,4})", full_text)
    if dob_match:
        parsed["dob"] = dob_match.group(1)

    # Gender
    gender_match = re.search(r"(?i)\b(male|female|transgender)\b", full_text)
    if gender_match:
        parsed["gender"] = gender_match.group(1).capitalize()

    # Address
    address = None
    for i, line in enumerate(lines):
        if re.search(r"(?i)^address[:\-]?", line):
            address = line.split(":", 1)[-1].strip()
            break

    if not address and parsed["aadhaarNumber"]:
        aadhaar_line_index = next(
            (i for i, l in enumerate(lines) if parsed["aadhaarNumber"][:4] in l.replace(" ", "")),
            None,
        )
        if aadhaar_line_index and aadhaar_line_index > 0:
            address = lines[aadhaar_line_index - 1]

    parsed["address"] = address
    return parsed


# -------------------- C. DOCUMENT UPLOAD + OCR --------------------
@app.post("/upload/")
async def upload_image(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    try:
        start_time = time.time()
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))

        # OCR Extraction
        text = pytesseract.image_to_string(image)
        parsed = parse_text(text)

        # Detect document type
        if parsed["aadhaarNumber"]:
            doc_type = "Aadhaar"
        elif parsed["panNumber"]:
            doc_type = "PAN"
        else:
            doc_type = "UNKNOWN"

        record = {
            "userId": str(user["_id"]),
            "filename": file.filename,
            "docType": doc_type,
            "rawText": text,
            "parsed": parsed,
            "processingTimeMs": int((time.time() - start_time) * 1000),
            "uploadedAt": datetime.utcnow().isoformat(),
        }

        record_id = documents_collection.insert_one(record).inserted_id
        record["_id"] = str(record_id)

        # Also store parsed data separately
        kyc_data_collection.insert_one(
            {
                "userId": str(user["_id"]),
                "docType": doc_type,
                "parsedData": parsed,
                "createdAt": datetime.utcnow().isoformat(),
            }
        )

        return JSONResponse(content=record)

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# -------------------- ROOT --------------------
@app.get("/")
def home():
    return {"message": "KYC OCR API (Signup + Login + Upload + OCR) is running successfully!"}
