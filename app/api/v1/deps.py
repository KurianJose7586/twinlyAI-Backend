# app/api/v1/deps.py

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from jose import JWTError, jwt
from app.core.config import settings
from app.schemas.user import User
from app.db.session import users_collection, api_keys_collection
from app.core.security import hash_api_key
from typing import Optional

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = await users_collection.find_one({"email": email})
    if user is None:
        raise credentials_exception
    
    user_model = User(**user, id=str(user["_id"]))
    return user_model

# --- NEW: Flexible Authentication Dependency ---
async def get_authenticated_user(
    token: Optional[str] = Depends(oauth2_scheme),
    api_key: Optional[str] = Depends(api_key_header)
) -> dict:
    """
    Validates credentials from either a JWT token or an API key.
    Returns the user document from the database.
    """
    if token:
        try:
            # Logic from get_current_user
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            email: str = payload.get("sub")
            if email is None:
                raise credentials_exception
            user = await users_collection.find_one({"email": email})
            if user:
                return user
        except JWTError:
            # Token is invalid, but we can fall through to check for an API key
            pass

    if api_key:
        # Logic from validate_api_key
        hashed_key = hash_api_key(api_key)
        key_doc = await api_keys_collection.find_one({"hashed_key": hashed_key})
        if key_doc:
            user = await users_collection.find_one({"_id": ObjectId(key_doc["user_id"])})
            if user:
                return user

    # If neither method succeeds, raise the exception
    raise credentials_exception