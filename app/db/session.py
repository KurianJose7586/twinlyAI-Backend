# app/db/session.py

from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

# Setup the MongoDB client and database
client = AsyncIOMotorClient(settings.MONGO_CONNECTION_STRING)
database = client[settings.MONGO_DB]

# Define collections
users_collection = database["users"]
bots_collection = database["bots"]
api_keys_collection = database["api_keys"] # <-- Add this new collection