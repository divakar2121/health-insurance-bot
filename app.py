import os
import uuid
import hashlib
import re
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Text,
    Integer,
    Float,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from PyPDF2 import PdfReader
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(32)
CORS(app)

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///instance/insurance_chatbot.db")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)
Session = sessionmaker(bind=engine)
Base = declarative_base()


class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True)
    filename = Column(String)
    content = Column(Text)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    chunks = relationship("Chunk", back_populates="document")


class Chunk(Base):
    __tablename__ = "chunks"
    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"))
    chunk_index = Column(Integer)
    text = Column(Text)
    document = relationship("Document", back_populates="chunks")


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    messages = relationship("Message", back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True)
    conversation_id = Column(String, ForeignKey("conversations.id"))
    role = Column(String)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    conversation = relationship("Conversation", back_populates="messages")


class QAHistory(Base):
    __tablename__ = "qa_history"
    id = Column(String, primary_key=True)
    question = Column(Text)
    answer = Column(Text)
    document_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


try:
    Base.metadata.create_all(engine)
    print("Database tables created/verified!")
except Exception as e:
    print(f"Database connection issue: {e}")
    print("App will try to reconnect on first request")

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

FALLBACK_MODEL = "meta-llama/llama-3.1-8b-instruct"
FREE_MODEL = "meta-llama/llama-3.1-8b-instruct"  # Use Llama instead of Gemma


def call_llm(messages, model=None, temperature=0.7):
    if not OPENROUTER_API_KEY:
        print("ERROR: No API key!")
        return "Error: OpenRouter API key not configured"

    if model is None:
        model = FREE_MODEL

    print(f"Using model: {model}")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.environ.get("APP_URL", "http://localhost:5000"),
        "X-Title": "Health Insurance Chatbot",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 4000,
    }
    try:
        import requests as req

        resp = req.post(OPENROUTER_URL, json=payload, headers=headers, timeout=60)

        if resp.status_code == 401:
            return "Error: API key expired or invalid. Please get a new key from https://openrouter.ai"
        if resp.status_code == 400:
            if model != FALLBACK_MODEL:
                return call_llm(messages, model=FALLBACK_MODEL, temperature=temperature)
            return "Error: Bad request. Please check API key and try again."
        if resp.status_code != 200:
            return f"Error: {resp.status_code} {resp.text[:200]}"

        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error: {str(e)}"


def chunk_text(text):
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    current_chunk = []
    current_size = 0

    for sentence in sentences:
        if current_size + len(sentence) > 1000:
            if current_chunk:
                chunks.append(" ".join(current_chunk))
            current_chunk = [sentence]
            current_size = len(sentence)
        else:
            current_chunk.append(sentence)
            current_size += len(sentence)

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def get_db():
    return Session()


def find_relevant_chunks(question, db):
    question_lower = question.lower()
    keywords = [w for w in re.findall(r"\w+", question_lower) if len(w) > 3]

    chunks = db.query(Chunk).all()
    scored = []

    for chunk in chunks:
        score = sum(1 for kw in keywords if kw in chunk.text.lower())
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c[1].text for _, c in scored[:3]]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/documents", methods=["GET"])
def get_documents():
    db = get_db()
    docs = db.query(Document).order_by(Document.uploaded_at.desc()).all()
    result = [
        {
            "id": d.id,
            "filename": d.filename,
            "uploaded_at": d.uploaded_at.isoformat(),
            "chunks": len(d.chunks),
        }
        for d in docs
    ]
    db.close()
    return jsonify(result)


@app.route("/api/documents", methods=["POST"])
def upload_document():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    filename = file.filename
    text = ""

    if filename.endswith(".pdf"):
        reader = PdfReader(file)
        for page in reader.pages:
            text += page.extract_text() or ""
    else:
        text = file.read().decode("utf-8", errors="ignore")

    doc_id = str(uuid.uuid4())
    db = get_db()

    doc = Document(id=doc_id, filename=filename, content=text[:50000])
    db.add(doc)

    chunks = chunk_text(text)
    for i, chunk in enumerate(chunks):
        chunk_obj = Chunk(
            id=str(uuid.uuid4()), document_id=doc_id, chunk_index=i, text=chunk
        )
        db.add(chunk_obj)

    db.commit()
    db.close()

    return jsonify({"id": doc_id, "filename": filename, "chunks": len(chunks)})


@app.route("/api/documents/<doc_id>", methods=["DELETE"])
def delete_document(doc_id):
    db = get_db()
    doc = db.query(Document).filter_by(id=doc_id).first()
    if doc:
        db.query(Chunk).filter_by(document_id=doc_id).delete()
        db.delete(doc)
        db.commit()
    db.close()
    return jsonify({"success": True})


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    question = data.get("question", "")
    conv_id = data.get("conversation_id")

    if not conv_id:
        conv_id = str(uuid.uuid4())

    db = get_db()

    if not db.query(Conversation).filter_by(id=conv_id).first():
        conv = Conversation(id=conv_id)
        db.add(conv)

    user_msg = Message(
        id=str(uuid.uuid4()), conversation_id=conv_id, role="user", content=question
    )
    db.add(user_msg)

    latest_doc = db.query(Document).order_by(Document.uploaded_at.desc()).first()
    doc_context = latest_doc.content if latest_doc else ""

    system_prompt = """You are a helpful Health Insurance Advisor for Indian clients. 
Use the provided document context to answer questions accurately.
If no context is provided, use your general knowledge about Indian health insurance.

Key topics to help with:
- Health insurance policy analysis
- IRDAI regulations and rights
- Premium calculation
- Claim procedures
- Policy comparison

Be concise and helpful."""

    if doc_context:
        system_prompt += f"\n\nDOCUMENT CONTENT:\n{doc_context[:8000]}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    answer = call_llm(messages)

    ai_msg = Message(
        id=str(uuid.uuid4()), conversation_id=conv_id, role="assistant", content=answer
    )
    db.add(ai_msg)

    qa = QAHistory(
        id=str(uuid.uuid4()),
        question=question,
        answer=answer,
        document_id=latest_doc.id if latest_doc else None,
    )
    db.add(qa)

    db.commit()
    db.close()

    return jsonify({"conversation_id": conv_id, "answer": answer})


@app.route("/api/qa-history", methods=["GET"])
def get_qa_history():
    db = get_db()
    history = db.query(QAHistory).order_by(QAHistory.id.desc()).limit(50).all()
    result = [
        {
            "id": h.id,
            "question": h.question,
            "answer": h.answer,
            "created_at": str(h.created_at),
        }
        for h in history
    ]
    db.close()
    return jsonify(result)


@app.route("/api/chunks", methods=["GET"])
def get_chunks():
    doc_id = request.args.get("document_id")
    db = get_db()
    if doc_id:
        chunks = db.query(Chunk).filter_by(document_id=doc_id).all()
    else:
        chunks = db.query(Chunk).limit(20).all()
    result = [
        {"id": c.id, "text": c.text[:200] + "...", "index": c.chunk_index}
        for c in chunks
    ]
    db.close()
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
