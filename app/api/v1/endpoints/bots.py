import os
import shutil
import re
from typing import List
from bson import ObjectId

from fastapi import (
    APIRouter, UploadFile, File, Depends, HTTPException, status
)
from starlette.responses import StreamingResponse, JSONResponse
from langchain_core.messages import HumanMessage, AIMessage

from app.api.v1.deps import get_current_user, get_authenticated_user
from app.schemas.user import User
from app.schemas.bot import Bot, BotCreate, BotUpdate
from app.db.session import bots_collection
from app.core.rag_pipeline import RAGPipeline, get_file_extension # Corrected import

router = APIRouter()

def strip_think_tags(text: str) -> str:
    """Removes <think> tags and surrounding whitespace from the LLM response."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

# This is the helper function that will clean the stream
async def clean_stream(generator):
    """An async generator that cleans chunks from the RAG pipeline stream."""
    async for chunk in generator:
        if "answer" in chunk:
            cleaned_chunk = strip_think_tags(chunk["answer"])
            if cleaned_chunk:
                yield cleaned_chunk

@router.post("/{bot_id}/chat/stream")
async def chat_with_bot_stream(bot_id: str, request_data: dict, authenticated_user: dict = Depends(get_authenticated_user)):
    user_message = request_data.get("message")
    chat_history_raw = request_data.get("chat_history", [])

    bot = await bots_collection.find_one({"_id": ObjectId(bot_id)})
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    user_id_from_auth = str(authenticated_user.get("_id"))
    if str(bot.get("user_id")) != user_id_from_auth:
        raise HTTPException(status_code=403, detail="You do not have permission for this bot")

    pipeline = RAGPipeline(bot_id=bot_id, user_id=user_id_from_auth, bot_name=bot["name"])

    chat_history = [HumanMessage(content=msg["content"]) if msg["type"] == "user" else AIMessage(content=msg["content"]) for msg in chat_history_raw]

    # --- THIS IS THE FIX ---
    # Wrap the pipeline's stream with the clean_stream function.
    return StreamingResponse(
        clean_stream(pipeline.get_response_stream(user_message, chat_history)),
        media_type="text/event-stream"
    )

@router.post("/{bot_id}/chat")
async def chat_with_bot(bot_id: str, request_data: dict, authenticated_user: dict = Depends(get_authenticated_user)):
    user_message = request_data.get("message")
    chat_history_raw = request_data.get("chat_history", [])
    
    bot = await bots_collection.find_one({"_id": ObjectId(bot_id)})
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    if str(bot.get("user_id")) != str(authenticated_user.get("_id")):
        raise HTTPException(status_code=403, detail="You do not have permission for this bot")

    pipeline = RAGPipeline(bot_id=bot_id, user_id=str(bot["user_id"]), bot_name=bot["name"])
    chat_history = [HumanMessage(content=msg["content"]) if msg["type"] == "user" else AIMessage(content=msg["content"]) for msg in chat_history_raw]
    
    # Also ensure the non-streaming endpoint is properly cleaned
    full_response = ""
    async for chunk in pipeline.get_response_stream(user_message, chat_history):
        if "answer" in chunk:
            full_response += chunk["answer"]
            
    return {"reply": strip_think_tags(full_response)}


# (The rest of your endpoints remain the same)
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
async def create_bot(bot_in: BotCreate, current_user: User = Depends(get_current_user)):
    bot_doc = {"name": bot_in.name, "user_id": str(current_user.id)}
    result = await bots_collection.insert_one(bot_doc)
    created_bot = await bots_collection.find_one({"_id": result.inserted_id})
    return created_bot

@router.post("/{bot_id}/upload", status_code=status.HTTP_200_OK)
async def upload_bot_resume(bot_id: str, file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    bot = await bots_collection.find_one({"_id": ObjectId(bot_id)})
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    if str(bot.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized to upload to this bot")

    user_id = str(current_user.id)
    file_extension = get_file_extension(file.filename)
    if not file_extension:
        raise HTTPException(status_code=400, detail="Invalid file type")

    upload_dir = f"data/{user_id}/{bot_id}"
    if os.path.exists(upload_dir):
        shutil.rmtree(upload_dir)
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, f"resume{file_extension}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        pipeline = RAGPipeline(bot_id=bot_id, user_id=user_id, bot_name=bot.get("name"))
        await pipeline.load_and_index_document(file_path) # Changed from process_file
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process and index the document: {str(e)}")

    return JSONResponse(content={"message": f"File '{file.filename}' uploaded and indexed successfully for bot '{bot.get('name')}'."})

@router.get("/", response_model=List[Bot])
async def get_user_bots(current_user: User = Depends(get_current_user)):
    bots = await bots_collection.find({"user_id": str(current_user.id)}).to_list(100)
    return bots

@router.patch("/{bot_id}", response_model=Bot)
async def update_bot(bot_id: str, bot_in: BotUpdate, current_user: User = Depends(get_current_user)):
    bot = await bots_collection.find_one({"_id": ObjectId(bot_id), "user_id": str(current_user.id)})
    if not bot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found")
        
    update_data = bot_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")
        
    await bots_collection.update_one({"_id": ObjectId(bot_id)}, {"$set": update_data})
    updated_bot = await bots_collection.find_one({"_id": ObjectId(bot_id)})
    return updated_bot

@router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bot(bot_id: str, current_user: User = Depends(get_current_user)):
    bot = await bots_collection.find_one({"_id": ObjectId(bot_id), "user_id": str(current_user.id)})
    if not bot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found")

    await bots_collection.delete_one({"_id": ObjectId(bot_id)})
    
    user_data_dir = os.path.join("data", str(current_user.id), bot_id)
    if os.path.exists(user_data_dir):
        shutil.rmtree(user_data_dir)
    return