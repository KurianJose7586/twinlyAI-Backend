# app/api/v1/endpoints/users.py

from fastapi import APIRouter, Depends
from app.schemas.user import User
from app.api.v1.deps import get_current_user

router = APIRouter()

@router.get("/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Get current logged-in user.
    """
    return current_user