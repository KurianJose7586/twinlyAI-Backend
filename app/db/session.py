# TwinlyAI-Backend/app/db/session.py
# Database engine and session management

import motor.motor_asyncio
from app.core.config import settings
from pymongo.database import Database
from motor.motor_asyncio import AsyncIOMotorCollection

# Create a new asynchronous client to a single MongoDB instance.
# The client is created using the connection string from your .env file.
client = motor.motor_asyncio.AsyncIOMotorClient(settings.MONGO_CONNECTION_STRING)

# Get a reference to the database.
# If the database doesn't exist, MongoDB will create it on the first write operation.
# We'll name our database "twinlyai_db".
db: Database = client.twinlyai_db

# --- Collection Handles ---
# Get a reference to the specific collections (equivalent to tables in SQL)
# that we will be working with. This allows us to import these collection
# objects directly in other parts of the application to interact with the data.

users_collection: AsyncIOMotorCollection = db.get_collection("users")
bots_collection: AsyncIOMotorCollection = db.get_collection("bots")


# --- Optional: Dependency for Routes ---
# You can create a dependency function to be used in your API routes.
# While you can import 'db' directly, using a dependency can be useful
# for more complex setups, like handling different databases for testing.
async def get_database() -> Database:
    """
    Dependency function that returns the database instance.
    """
    return db