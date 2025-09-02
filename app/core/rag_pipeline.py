# app/core/rag_pipeline.py

import re
import os
import json
from pathlib import Path
import pdfplumber
from docx import Document as DocxDocument
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AIMessage

# --- CONFIGURATION ---
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
embedding_model = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")

# --- JSON to TEXT CONVERSION ---
def json_to_text(json_data: dict) -> str:
    # (This function remains unchanged)
    text = ""
    for key, value in json_data.items():
        if isinstance(value, dict):
            text += f"{key.replace('_', ' ').title()}:\n"
            for sub_key, sub_value in value.items():
                text += f"  {sub_key.replace('_', ' ').title()}: {sub_value}\n"
        elif isinstance(value, list):
            text += f"{key.replace('_', ' ').title()}:\n"
            for item in value:
                if isinstance(item, dict):
                    for item_key, item_value in item.items():
                        text += f"  - {item_key.replace('_', ' ').title()}: {item_value}\n"
                else:
                    text += f"- {item}\n"
        else:
            text += f"{key.replace('_', ' ').title()}: {value}\n"
    return text

# --- FILE PROCESSING ---
def extract_text_from_file(file_path: Path) -> str:
    # (This function remains unchanged)
    if file_path.suffix == ".pdf":
        with pdfplumber.open(file_path) as pdf:
            return "".join(page.extract_text() for page in pdf.pages)
    elif file_path.suffix == ".docx":
        doc = DocxDocument(file_path)
        return "\n".join(para.text for para in doc.paragraphs)
    elif file_path.suffix == ".txt":
        return file_path.read_text(encoding="utf-8")
    elif file_path.suffix == ".json":
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return json_to_text(data)
    else:
        raise ValueError(f"Unsupported file type: {file_path.suffix}")

# --- RAG PIPELINE CORE ---
def create_and_persist_index(file_path: Path, bot_id: str):
    # (This function remains unchanged)
    text_content = extract_text_from_file(file_path)
    documents = [Document(page_content=text_content)]
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.split_documents(documents)
    
    vector_store = FAISS.from_documents(chunks, embedding_model)
    
    user_index_dir = DATA_DIR / bot_id
    user_index_dir.mkdir(exist_ok=True)
    vector_store.save_local(str(user_index_dir / "faiss_index"))

# --- MODIFIED FUNCTION ---
def get_rag_chain(user_id: str, bot_name: str):
    user_index_path = str(DATA_DIR / user_id / "faiss_index")
    if not Path(user_index_path).exists():
        return None

    vector_store = FAISS.load_local(
        user_index_path, 
        embedding_model, 
        allow_dangerous_deserialization=True
    )
    retriever = vector_store.as_retriever()
    
    llm = ChatGroq(temperature=0.2, model_name="qwen/qwen3-32b")

    # --- NEW PROMPT WITH MEMORY ---
    # This prompt now includes a placeholder for chat history
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""
You are "{bot_name}," a professional AI assistant. Your task is to answer questions about a person based on their resume provided in the context.

**Persona & Introduction:**
- Your name is "{bot_name}".
- **Introduce yourself ONLY IF it is the first turn of the conversation or if asked "who are you?".**
- Your introduction should be: "Hello, I am {bot_name}, an AI assistant for [Person's Name]. I can answer questions based on their resume. How can I help?"
- You must extract the [Person's Name] from the context.
- Always speak about the person in the third person (e.g., "He has experience in...").

**Response Guidelines:**
- Answer exclusively from the <context>.
- If the information isn't in the context, politely state that.
- Use Markdown (bolding, bullet points) for clarity.
- For personal or off-topic questions, state that you can only answer professional questions based on the resume.

<context>
{{context}}
</context>
"""),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
    ])

    document_chain = create_stuff_documents_chain(llm, prompt)
    return create_retrieval_chain(retriever, document_chain)