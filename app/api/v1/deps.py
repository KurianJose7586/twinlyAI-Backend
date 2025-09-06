# app/api/v1/deps.py

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from jose import JWTError, jwt
from app.core.config import settings
from app.schemas.user import User
from app.db.session import users_collection, api_keys_collection
# --- IMPORT from the new location to break the cycle ---
from app.core.security import hash_api_key 

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

async def validate_api_key(api_key: str = Depends(api_key_header)):
    """
    Validates an API key provided in the 'X-API-Key' header.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key is missing"
        )
    
    hashed_key = hash_api_key(api_key)
    
    key_doc = await api_keys_collection.find_one({"hashed_key": hashed_key})
    
    if not key_doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )
    
    return key_doc