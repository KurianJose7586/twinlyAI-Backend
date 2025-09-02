# app/db/session.py

from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

# Setup the MongoDB client and database
client = AsyncIOMotorClient(settings.MONGO_CONNECTION_STRING)
# --- THIS IS THE FIX ---
# Change MONGO_DB to MONGO_DB_NAME to match the variable in your config file.
database = client[settings.MONGO_DB_NAME]
# --- END OF FIX ---

# Define collections
users_collection = database["users"]
bots_collection = database["bots"]
api_keys_collection = database["api_keys"]