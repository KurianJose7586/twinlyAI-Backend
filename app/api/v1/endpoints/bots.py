import os
import shutil
import re
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, StreamingResponse
from bson import ObjectId
from typing import List

from app.db.session import get_db
from app.core.rag_pipeline import RAGPipeline, get_file_extension
from app.api.v1.deps import get_current_user, get_authenticated_user, api_key_auth
from app.schemas.bot import BotCreate, BotUpdate
from langchain_core.messages import HumanMessage, AIMessage

router = APIRouter()
bots_collection = get_db()["bots"]

def strip_think_tags(text: str) -> str:
    """Removes <think> tags from the LLM response for a cleaner output."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

async def clean_stream(generator):
    """An async generator that cleans chunks from the RAG pipeline stream."""
    async for chunk in generator:
        if "answer" in chunk:
            cleaned_chunk = strip_think_tags(chunk["answer"])
            if cleaned_chunk: # Only yield if there's content after stripping
                yield cleaned_chunk

@router.get("/public/{bot_id}")
async def get_public_bot_info(bot_id: str):
    bot = await bots_collection.find_one({"_id": ObjectId(bot_id)})
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    return {"name": bot.get("name"), "id": str(bot.get("_id"))}

@router.post("/create", status_code=201)
async def create_bot(bot_data: BotCreate, current_user: dict = Depends(get_current_user)):
    bot_doc = {
        "name": bot_data.name,
        "user_id": current_user["_id"]
    }
    result = await bots_collection.insert_one(bot_doc)
    created_bot = await bots_collection.find_one({"_id": result.inserted_id})
    return created_bot

@router.post("/{bot_id}/upload")
async def upload_bot_resume(bot_id: str, file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    bot = await bots_collection.find_one({"_id": ObjectId(bot_id)})
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    if str(bot.get("user_id")) != str(current_user.get("_id")):
        raise HTTPException(status_code=403, detail="Not authorized to upload to this bot")

    user_id = str(current_user["_id"])
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
        await pipeline.load_and_index_document(file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process and index the document: {str(e)}")

    return JSONResponse(content={"message": f"File '{file.filename}' uploaded and indexed successfully for bot '{bot.get('name')}'."})

@router.get("/")
async def get_user_bots(current_user: dict = Depends(get_current_user)):
    user_id = current_user["_id"]
    bots_cursor = bots_collection.find({"user_id": user_id})
    user_bots = await bots_cursor.to_list(length=None)
    return user_bots

@router.patch("/{bot_id}")
async def update_bot(bot_id: str, bot_update: BotUpdate, current_user: dict = Depends(get_current_user)):
    bot = await bots_collection.find_one({"_id": ObjectId(bot_id)})
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    if str(bot.get("user_id")) != str(current_user.get("_id")):
        raise HTTPException(status_code=403, detail="Not authorized to update this bot")

    update_data = bot_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")

    await bots_collection.update_one({"_id": ObjectId(bot_id)}, {"$set": update_data})
    updated_bot = await bots_collection.find_one({"_id": ObjectId(bot_id)})
    return updated_bot

@router.delete("/{bot_id}", status_code=204)
async def delete_bot(bot_id: str, current_user: dict = Depends(get_current_user)):
    bot = await bots_collection.find_one({"_id": ObjectId(bot_id)})
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    if str(bot.get("user_id")) != str(current_user.get("_id")):
        raise HTTPException(status_code=403, detail="Not authorized to delete this bot")

    # Delete associated data directory
    user_id = str(current_user["_id"])
    bot_data_dir = f"data/{user_id}/{bot_id}"
    if os.path.exists(bot_data_dir):
        shutil.rmtree(bot_data_dir)

    # Delete from MongoDB
    await bots_collection.delete_one({"_id": ObjectId(bot_id)})
    return

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
    
    response = await pipeline.get_response(user_message, chat_history)
    response['answer'] = strip_think_tags(response['answer'])
    return response

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

    return StreamingResponse(
        clean_stream(pipeline.get_response_stream(user_message, chat_history)),
        media_type="text/event-stream"
    )