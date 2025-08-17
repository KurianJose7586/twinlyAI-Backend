# app/schemas/bot.py
from pydantic import BaseModel, Field
from .pyobjectid import PyObjectId

class BotBase(BaseModel):
    name: str

class BotCreate(BotBase):
    pass

class Bot(BotBase):
    id: PyObjectId = Field(..., alias="_id")
    user_id: str

    class Config:
        from_attributes = True
        populate_by_name = True
        json_encoders = {PyObjectId: str}