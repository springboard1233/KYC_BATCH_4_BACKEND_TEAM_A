from motor.motor_asyncio import AsyncIOMotorClient
from .config import MONGO_URI, DB_NAME

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]

# Collections
users_coll = db.get_collection("users")
documents_coll = db.get_collection("uploaded_documents")
kyc_coll = db.get_collection("extracted_kyc")
