# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.v1.endpoints import auth, bots 

# This is the crucial line. The variable MUST be named 'app'.
app = FastAPI(title="TwinlyAI Backend")

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    """
    Root endpoint to confirm the server is running.
    """
    return {"message": "Welcome to the TwinlyAI API!"}

# --- API Routers ---
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(bots.router, prefix="/api/v1/bots", tags=["Bots"])