# app/schemas/bot.py

from pydantic import BaseModel, Field
from typing import Optional
from .pyobjectid import PyObjectId
from bson import ObjectId

class BotBase(BaseModel):
    name: str

class BotCreate(BotBase):
    pass

# --- NEW: Add a model for updating the bot ---
class BotUpdate(BaseModel):
    name: str

class Bot(BotBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    user_id: Optional[str] = None

    class Config:
        json_encoders = {ObjectId: str}
        populate_by_name = True
        arbitrary_types_allowed = True