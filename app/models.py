from pydantic import BaseModel
from typing import Optional, Dict, Any

class ParsedKYC(BaseModel):
    panNumber: Optional[str]
    aadhaarNumber: Optional[str]
    name: Optional[str]
    fatherName: Optional[str]
    dob: Optional[str]
    gender: Optional[str]
    address: Optional[str]

class KYCResponse(BaseModel):
    docType: Optional[str]
    rawText: str
    parsed: ParsedKYC
    processingTimeMs: int
