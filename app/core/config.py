# Application settings from environment variables

# app/core/config.py

from pydantic_settings import BaseSettings
from dotenv import load_dotenv 

load_dotenv()  

class Settings(BaseSettings):
    """
    Application settings are loaded from environment variables.
    """
    MONGO_CONNECTION_STRING: str
    SECRET_KEY: str
    GROQ_API_KEY: str 
    # Default algorithm for JWT
    ALGORITHM: str = "HS256"
    MONGO_CONNECTION_STRING: str
    MONGO_DB_NAME: str = "twinlyai_db" 
    # Token validity period in minutes
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GITHUB_CLIENT_ID: str
    GITHUB_CLIENT_SECRET: str

    class Config:
        env_file = ".env"

# Create a single instance of the settings to be imported in other files
settings = Settings()