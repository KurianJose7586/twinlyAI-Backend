# app/api/v1/endpoints/api_keys.py

import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from app.api.v1.deps import get_current_user
from app.schemas.user import User
from app.db.session import api_keys_collection
from bson import ObjectId
from typing import List
import hashlib

router = APIRouter()

# --- Helper to hash API keys for storage ---
def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()

class APIKeyResponse(dict):
    pass

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=APIKeyResponse)
async def create_api_key(
    current_user: User = Depends(get_current_user)
):
    """
    Generate a new API key for the current user.
    The key is stored hashed in the database.
    The unhashed key is returned to the user only once.
    """
    # Create a new secure, URL-safe key
    new_key = f"ta_{secrets.token_urlsafe(32)}"
    hashed_key = hash_api_key(new_key)
    
    api_key_doc = {
        "hashed_key": hashed_key,
        "user_id": str(current_user.id),
        "prefix": new_key[:5] # Store the first few chars for identification
    }
    
    await api_keys_collection.insert_one(api_key_doc)
    
    # Return the full, unhashed key to the user
    return {"api_key": new_key, "message": "Key created successfully. Please save it securely as you will not see it again."}


@router.get("/", response_model=List[dict])
async def get_user_api_keys(
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve a list of API key prefixes for the current user.
    """
    keys_cursor = api_keys_collection.find({"user_id": str(current_user.id)})
    keys = await keys_cursor.to_list(100)
    # Return only non-sensitive info
    return [{"id": str(key["_id"]), "prefix": key["prefix"]} for key in keys]


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Delete an API key.
    """
    result = await api_keys_collection.delete_one(
        {"_id": ObjectId(key_id), "user_id": str(current_user.id)}
    )
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="API key not found")
        
    return