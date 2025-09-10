# app/main.py

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.endpoints import auth, bots, api_keys, users # <-- Import users router

app = FastAPI(
    title="TwinlyAI API",
    description="API for the TwinlyAI SaaS application.",
    version="0.1.0"
)

# CORS Middleware
origins = [
    "http://localhost:3000",
    "https://twinly-ai-frontend.vercel.app/"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Router Setup
api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(bots.router, prefix="/bots", tags=["bots"])
api_router.include_router(api_keys.router, prefix="/api-keys", tags=["api-keys"])
api_router.include_router(users.router, prefix="/users", tags=["users"]) # <-- Include users router

app.include_router(api_router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "Welcome to TwinlyAI API"}