# Handles /login, /signup routes

# app/api/v1/endpoints/auth.py

from fastapi import APIRouter, HTTPException, status, Body
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.param_functions import Depends
from app.schemas.user import UserCreate, User, Token
from app.db.session import users_collection
from app.core.security import get_password_hash, verify_password, create_access_token
from pymongo.errors import DuplicateKeyError

router = APIRouter()

@router.post("/signup", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_user(user_in: UserCreate):
    """
    Create a new user.
    """
    hashed_password = get_password_hash(user_in.password)
    
    # Create a user document to insert into the database
    user_doc = {
        "email": user_in.email,
        "hashed_password": hashed_password
    }
    
    try:
        # Insert the new user into the database
        await users_collection.insert_one(user_doc)
    except DuplicateKeyError:
        # This assumes you have created a unique index on the 'email' field in MongoDB
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )
        
    # Find the newly created user to return its data (excluding password)
    created_user = await users_collection.find_one({"email": user_in.email})
    return created_user


@router.post("/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticate a user and return an access token.
    FastAPI's OAuth2PasswordRequestForm dependency automatically handles
    receiving 'username' and 'password' from a form body.
    """
    user = await users_collection.find_one({"email": form_data.username})
    
    # Check if the user exists and the password is correct
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # Create the access token
    access_token = create_access_token(
        data={"sub": user["email"]}
    )
    
    return {"access_token": access_token, "token_type": "bearer"}