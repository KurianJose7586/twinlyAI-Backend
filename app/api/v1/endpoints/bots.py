import os
import shutil
import re
from typing import List
from bson import ObjectId

from fastapi import (
    APIRouter, UploadFile, File, Depends, HTTPException, status
)
from starlette.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage

from app.api.v1.deps import get_current_user, get_authenticated_user
from app.schemas.user import User
from app.schemas.bot import Bot, BotCreate, BotUpdate
from app.db.session import bots_collection
from app.core.rag_pipeline import RAGPipeline

router = APIRouter()

def strip_think_tags(text: str) -> str:
    """Removes <think> tags from the LLM response for a cleaner output."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

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
    bot_doc = { "name": bot_in.name, "user_id": str(current_user.id) }
    result = await bots_collection.insert_one(bot_doc)
    created_bot = await bots_collection.find_one({"_id": result.inserted_id})
    return created_bot

@router.post("/{bot_id}/upload", status_code=status.HTTP_200_OK)
async def upload_resume(bot_id: str, file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    bot = await bots_collection.find_one({"_id": ObjectId(bot_id), "user_id": str(current_user.id)})
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    pipeline = RAGPipeline(bot_id=bot_id, user_id=str(current_user.id), bot_name=bot["name"])
    
    # Using /tmp for temporary file storage, which is common in serverless/containerized environments
    file_location = f"/tmp/{file.filename}"
    with open(file_location, "wb+") as file_object:
        shutil.copyfileobj(file.file, file_object)

    try:
        pipeline.process_file(file_location)
        return {"message": f"Successfully uploaded and indexed resume for bot '{bot['name']}'"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if os.path.exists(file_location):
            os.remove(file_location)

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
    
    full_response = ""
    async for chunk in pipeline.get_response_stream(user_message, chat_history):
        full_response += chunk

    return {"reply": strip_think_tags(full_response)}

@router.post("/{bot_id}/chat/stream")
async def chat_with_bot_stream(bot_id: str, request_data: dict, authenticated_user: dict = Depends(get_authenticated_user)):
    user_message = request_data.get("message")
    chat_history_raw = request_data.get("chat_history", [])

    bot = await bots_collection.find_one({"_id": ObjectId(bot_id)})
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    if str(bot.get("user_id")) != str(authenticated_user.get("_id")):
        raise HTTPException(status_code=403, detail="You do not have permission for this bot")

    pipeline = RAGPipeline(bot_id=bot_id, user_id=str(bot["user_id"]), bot_name=bot["name"])

    chat_history = [HumanMessage(content=msg["content"]) if msg["type"] == "user" else AIMessage(content=msg["content"]) for msg in chat_history_raw]

    # --- THIS IS THE FIX ---
    # Define a new async generator that wraps the original stream,
    # buffers the content, cleans it, and then yields the final result.
    async def clean_stream_generator():
        """
        Consumes the RAG pipeline stream, waits for the full response,
        cleans it, and then yields the single cleaned response.
        """
        full_response_chunks = []
        async for chunk in pipeline.get_response_stream(user_message, chat_history):
            # The RAG pipeline yields dictionaries, we need the 'answer' part
            if "answer" in chunk:
                 full_response_chunks.append(chunk["answer"])
        
        full_response = "".join(full_response_chunks)
        cleaned_response = strip_think_tags(full_response)
        yield cleaned_response
    # --- END OF FIX ---

    return StreamingResponse(
        clean_stream_generator(), # Use the new cleaning generator
        media_type="text/event-stream"
    )

@router.get("/", response_model=List[Bot])
async def get_user_bots(current_user: User = Depends(get_current_user)):
    bots = await bots_collection.find({"user_id": str(current_user.id)}).to_list(100)
    return bots
    
@router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bot(bot_id: str, current_user: User = Depends(get_current_user)):
    bot = await bots_collection.find_one({"_id": ObjectId(bot_id), "user_id": str(current_user.id)})
    if not bot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found")

    await bots_collection.delete_one({"_id": ObjectId(bot_id)})
    # Correctly construct the path for directory removal
    user_data_dir = os.path.join("data", str(current_user.id), bot_id)
    if os.path.exists(user_data_dir):
        shutil.rmtree(user_data_dir)
    return

@router.patch("/{bot_id}", response_model=Bot)
async def update_bot(bot_id: str, bot_in: BotUpdate, current_user: User = Depends(get_current_user)):
    bot = await bots_collection.find_one({"_id": ObjectId(bot_id), "user_id": str(current_user.id)})
    if not bot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found")
        
    update_data = bot_in.model_dump(exclude_unset=True)
    await bots_collection.update_one({"_id": ObjectId(bot_id)}, {"$set": update_data})
    updated_bot = await bots_collection.find_one({"_id": ObjectId(bot_id)})
    return updated_bot
