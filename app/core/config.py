# Application settings from environment variables

# app/core/config.py

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """
    Application settings are loaded from environment variables.
    """
    MONGO_CONNECTION_STRING: str
    SECRET_KEY: str
    GROQ_API_KEY: str 
    # Default algorithm for JWT
    ALGORITHM: str = "HS256"
    # Token validity period in minutes
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    class Config:
        env_file = ".env"

# Create a single instance of the settings to be imported in other files
settings = Settings()