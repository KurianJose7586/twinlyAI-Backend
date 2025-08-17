# Pydantic schemas for data validation (e.g., UserCreate)

# app/schemas/user.py

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from .pyobjectid import PyObjectId  


class UserBase(BaseModel):
    """
    Base user schema with common fields.
    """
    email: EmailStr

class UserCreate(UserBase):
    """
    Schema for creating a new user. Expects a password.
    """
    password: str

class UserInDB(UserBase):
    """
    Schema for user data as it is stored in the database.
    Includes the hashed password.
    """
    hashed_password: str

class User(UserBase):
    """
    Schema for user data returned from the API.
    Excludes the password for security.
    """
    id: PyObjectId = Field(..., alias="_id")

    class Config:
        # Allows Pydantic to work with non-dict objects (like MongoDB documents)
        from_attributes = True
        # Allows using "_id" from MongoDB as "id" in the schema
        populate_by_name = True

class Token(BaseModel):
    """
    Schema for the access token.
    """
    access_token: str
    token_type: str

class TokenData(BaseModel):
    """
    Schema for the data encoded within a JWT.
    """
    email: Optional[str] = None