# app/api/v1/endpoints/bots.py

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status, Body
from app.api.v1.deps import get_current_user, get_authenticated_user
from app.schemas.user import User
# --- Import the new BotUpdate schema ---
from app.schemas.bot import Bot, BotCreate, BotUpdate
from app.db.session import bots_collection
from app.core.rag_pipeline import DATA_DIR, create_and_persist_index, get_rag_chain
from typing import List
from bson import ObjectId
import re
from langchain_core.messages import HumanMessage, AIMessage
import shutil

router = APIRouter()

def strip_think_tags(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

# ... (get_public_bot_info, create_bot, upload_resume, chat_with_bot, get_user_bots, delete_bot endpoints remain the same) ...

@router.get("/public/{bot_id}")
async def get_public_bot_info(bot_id: str):
    try:
        bot = await bots_collection.find_one({"_id": ObjectId(bot_id)})
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        return {"id": str(bot["_id"]), "name": bot["name"]}
    except Exception:
        raise HTTPException(status_code=404, detail="Bot not found or invalid ID")

@router.post("/create", response_model=Bot, status_code=status.HTTP_201_CREATED)
async def create_bot(
    bot_in: BotCreate,
    current_user: User = Depends(get_current_user)
):
    bot_doc = { "name": bot_in.name, "user_id": str(current_user.id) }
    result = await bots_collection.insert_one(bot_doc)
    created_bot = await bots_collection.find_one({"_id": result.inserted_id})
    return created_bot

@router.post("/{bot_id}/upload", status_code=status.HTTP_200_OK)
async def upload_resume(
    bot_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    bot = await bots_collection.find_one({"_id": ObjectId(bot_id), "user_id": str(current_user.id)})
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
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
    authenticated_user: dict = Depends(get_authenticated_user)
):
    user_message = message.get("message")
    chat_history_raw = message.get("chat_history", [])
    if not user_message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    bot = await bots_collection.find_one({"_id": ObjectId(bot_id)})
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    if bot.get("user_id") != str(authenticated_user.get("_id")):
        raise HTTPException(status_code=403, detail="You do not have permission for this bot")

    rag_chain = get_rag_chain(bot_id, bot_name=bot["name"])
    if rag_chain is None:
        raise HTTPException(status_code=404, detail="Bot index not found. Please upload a resume.")

    chat_history = []
    for msg in chat_history_raw:
        if msg.get("type") == "user":
            chat_history.append(HumanMessage(content=msg.get("content")))
        elif msg.get("type") == "bot":
            chat_history.append(AIMessage(content=msg.get("content")))

    result = await rag_chain.ainvoke({"input": user_message, "chat_history": chat_history})
    raw_answer = result.get("answer", "Sorry, I couldn't find an answer.")
    clean_answer = strip_think_tags(raw_answer)
    return {"reply": clean_answer}

@router.get("/", response_model=List[Bot])
async def get_user_bots(current_user: User = Depends(get_current_user)):
    bots = await bots_collection.find({"user_id": str(current_user.id)}).to_list(100)
    return bots
    
@router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bot(
    bot_id: str,
    current_user: User = Depends(get_current_user)
):
    bot = await bots_collection.find_one(
        {"_id": ObjectId(bot_id), "user_id": str(current_user.id)}
    )
    if not bot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found")

    await bots_collection.delete_one({"_id": ObjectId(bot_id)})

    bot_dir = DATA_DIR / bot_id
    if bot_dir.exists() and bot_dir.is_dir():
        shutil.rmtree(bot_dir)

    return

# --- NEW: Bot Update Endpoint ---
@router.patch("/{bot_id}", response_model=Bot)
async def update_bot(
    bot_id: str,
    bot_in: BotUpdate,
    current_user: User = Depends(get_current_user)
):
    """
    Updates a bot's details, such as its name.
    """
    bot = await bots_collection.find_one(
        {"_id": ObjectId(bot_id), "user_id": str(current_user.id)}
    )
    if not bot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found")
        
    update_data = bot_in.model_dump(exclude_unset=True)
    
    await bots_collection.update_one(
        {"_id": ObjectId(bot_id)},
        {"$set": update_data}
    )
    
    updated_bot = await bots_collection.find_one({"_id": ObjectId(bot_id)})
    return updated_bot