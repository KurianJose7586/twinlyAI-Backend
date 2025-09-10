# TwinlyAI - Backend

Welcome to the backend of TwinlyAI! This is a powerful, asynchronous API built with FastAPI that serves as the engine for the TwinlyAI SaaS application. It handles everything from user authentication to the core AI and RAG (Retrieval-Augmented Generation) pipeline.

## ✨ Features

- **Secure Authentication**: Robust JWT-based authentication for user signup and login.
- **Multi-tenant Bot Management**: Full CRUD (Create, Read, Update, Delete) functionality for managing user-specific AI bots.
- **Document Processing**: Ingests various file types (`.pdf`, `.docx`, `.txt`, `.json`) to train the AI.
- **Advanced RAG Pipeline**: Utilizes LangChain to create vector embeddings (with FAISS) from documents and generate context-aware responses using the Groq LLM.
- **API Key Management**: Securely generate, manage, and validate API keys for public/programmatic access.
- **Flexible Security**: Endpoints that can be secured by either a user's login token (for dashboard use) or an API key (for public embeds).

## 🚀 Getting Started

Follow these instructions to get the backend server up and running on your local machine for development and testing.

### Prerequisites

- Python 3.10+
- A MongoDB Atlas account and a connection string.
- A Groq API key.

### Installation & Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/KurianJose7586/twinlyAI-Backend.git
    cd TwinlyAI-Backend
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    # For Windows
    python -m venv venv
    .\venv\Scripts\activate

    # For macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up environment variables:**
    Create a file named `.env` in the root of the backend directory and add the following variables.

    ```env
    # .env.example
    MONGO_CONNECTION_STRING="mongodb+srv://<user>:<password>@<cluster-url>/"
    MONGO_DB_NAME="twinlyai_db"
    GROQ_API_KEY="your_groq_api_key"

    # JWT Settings
    SECRET_KEY="a_very_secret_key_for_jwt_signing" # Generate a strong secret key
    ALGORITHM="HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES=60
    ```

### Running the Server

To run the backend development server, use the following command:
The server will be available at [http://127.0.0.1:8000](http://127.0.0.1:8000). The `--reload` flag enables hot-reloading for development.

## 📁 Project Structure

The backend follows a modular structure for scalability and maintainability.

- `app/main.py`: The entry point of the FastAPI application.
- `app/api/v1/`: Contains all the API logic for version 1.
  - `endpoints/`: Defines the API routes (auth.py, bots.py, users.py, api_keys.py).
  - `deps.py`: Manages dependencies and authentication logic (get_current_user, validate_api_key).
- `app/core/`: Core application logic.
  - `config.py`: Manages environment variables using Pydantic.
  - `security.py`: Handles password hashing, JWT creation, and API key hashing.
  - `rag_pipeline.py`: Contains all the logic for the RAG pipeline.
- `app/db/`: Database connection and session management.
- `app/schemas/`: Pydantic models for data validation and serialization.
- `data/`: Directory where uploaded documents and FAISS indexes are stored.

## 🛠️ API Endpoints

- **POST** `/api/v1/auth/signup` → Create a new user (Public)  
- **POST** `/api/v1/auth/login` → Log in and get a JWT token (Public)  
- **GET** `/api/v1/users/me` → Get the current logged-in user's details (JWT)  
- **GET** `/api/v1/bots/` → Get all bots for the current user (JWT)  
- **POST** `/api/v1/bots/create` → Create a new bot (JWT)  
- **PATCH** `/api/v1/bots/{bot_id}` → Update a bot's name (JWT)  
- **DELETE** `/api/v1/bots/{bot_id}` → Delete a bot and its data (JWT)  
- **POST** `/api/v1/bots/{bot_id}/upload` → Upload a document to train a bot (JWT)  
- **POST** `/api/v1/bots/{bot_id}/chat` → Chat with a specific bot (JWT/API Key)  
- **GET** `/api/v1/bots/public/{bot_id}` → Get public info for an embedded bot (Public)  
- **GET** `/api/v1/api-keys/` → Get a list of the user's API keys (JWT)  
- **POST** `/api/v1/api-keys/` → Generate a new API key (JWT)  
- **DELETE** `/api/v1/api-keys/{key_id}` → Delete an API key (JWT)  


```bash
uvicorn app.main:app --reload
