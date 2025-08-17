# app/api/v1/endpoints/bots.py

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status, Body
from app.api.v1.deps import get_current_user
from app.schemas.user import User
from app.schemas.bot import Bot, BotCreate
from app.db.session import bots_collection, users_collection
from app.core.rag_pipeline import DATA_DIR, create_and_persist_index, get_rag_chain
from typing import List
from bson import ObjectId  # <--- IMPORT ObjectId

router = APIRouter()

@router.post("/create", response_model=Bot, status_code=status.HTTP_201_CREATED)
async def create_bot(
    bot_in: BotCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Creates a new bot record in the database.
    """
    bot_doc = {
        "name": bot_in.name,
        "user_id": str(current_user.id)
    }
    result = await bots_collection.insert_one(bot_doc)
    created_bot = await bots_collection.find_one({"_id": result.inserted_id})
    return created_bot

@router.post("/{bot_id}/upload", status_code=status.HTTP_200_OK)
async def upload_resume(
    bot_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Handles resume upload for a specific bot.
    """
    # --- CHANGE THIS LINE ---
    bot = await bots_collection.find_one({"_id": ObjectId(bot_id), "user_id": str(current_user.id)})
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    # The bot_id is used for the directory name, which should be a string
    bot_dir = DATA_DIR / bot_id 
    bot_dir.mkdir(exist_ok=True)
    
    file_path = bot_dir / file.filename
    
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
        
    try:
        create_and_persist_index(file_path, bot_id)
        return {"message": f"Successfully uploaded and indexed for bot {bot['name']}"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{bot_id}/chat")
async def chat_with_bot(
    bot_id: str,
    message: dict = Body(...),
    current_user: User = Depends(get_current_user)
):
    """
    Handles chat queries for a specific bot.
    """
    user_message = message.get("message")
    if not user_message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # --- CHANGE THIS LINE ---
    bot = await bots_collection.find_one({"_id": ObjectId(bot_id), "user_id": str(current_user.id)})
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
            
    rag_chain = get_rag_chain(bot_id)
    
    if rag_chain is None:
        raise HTTPException(status_code=404, detail="Bot index not found. Please upload a resume for this bot.")
            
    result = await rag_chain.ainvoke({"input": user_message})
    
    return {"reply": result.get("answer", "Sorry, I couldn't find an answer.")}

@router.get("/", response_model=List[Bot])
async def get_user_bots(current_user: User = Depends(get_current_user)):
    """
    Retrieves all bots associated with the current user.
    """
    bots = await bots_collection.find({"user_id": str(current_user.id)}).to_list(100)
    return bots