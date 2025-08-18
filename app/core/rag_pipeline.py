# app/core/rag_pipeline.py

import re 
import os
import json
from pathlib import Path
import pdfplumber
from docx import Document as DocxDocument
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores.faiss import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document

# --- CONFIGURATION ---
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
embedding_model = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")

# --- JSON to TEXT CONVERSION (from your app.py) ---
def json_to_text(json_data: dict) -> str:
    """
    Converts the structured JSON from a resume into a single string.
    """
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


# --- MODIFIED FILE PROCESSING ---
def extract_text_from_file(file_path: Path) -> str:
    """Extracts text content from PDF, DOCX, TXT, or JSON files."""
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
def create_and_persist_index(file_path: Path, user_id: str):
    """
    Creates a FAISS vector index from a file and saves it to disk.
    """
    text_content = extract_text_from_file(file_path)
    documents = [Document(page_content=text_content)]
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.split_documents(documents)
    
    vector_store = FAISS.from_documents(chunks, embedding_model)
    
    user_index_dir = DATA_DIR / user_id
    user_index_dir.mkdir(exist_ok=True)
    vector_store.save_local(str(user_index_dir / "faiss_index"))

def get_rag_chain(user_id: str):
    """
    Loads a user's FAISS index and creates a RAG chain for querying.
    """
    user_index_path = str(DATA_DIR / user_id / "faiss_index")
    if not Path(user_index_path).exists():
        return None

    vector_store = FAISS.load_local(
        user_index_path, 
        embedding_model, 
        allow_dangerous_deserialization=True # Required for FAISS with LangChain
    )
    retriever = vector_store.as_retriever()
    
    # Using the LLM and prompt from your app.py
    llm = ChatGroq(temperature=0, model_name="qwen/qwen3-32b")
    prompt = ChatPromptTemplate.from_template("""
You are **Twinly**, the user’s personal AI assistant.

Guidelines:
- Answer ONLY using the information in <context>.
- Be concise and clear (2–4 sentences max).
- Use bullet points if listing multiple items.
- Highlight key skills, roles, or achievements simply.
- If the context does not contain the answer, reply: 
  "I don’t know based on the resume."

<context>
{context}
</context>

Question: {input}

Answer:
""")


    document_chain = create_stuff_documents_chain(llm, prompt)
    return create_retrieval_chain(retriever, document_chain)