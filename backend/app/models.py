from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Float, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(512), nullable=False, index=True)
    file_type = Column(String(10), nullable=False)  # txt, md, pdf
    file_size = Column(Integer, nullable=False)  # bytes
    upload_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    chunk_count = Column(Integer, default=0)
    collection = Column(String(128), default="Default", nullable=False)  # which ChromaDB collection
    chroma_doc_id = Column(String(256), nullable=True)  # safe_name used in ChromaDB


class QueryLog(Base):
    __tablename__ = "query_logs"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    source_count = Column(Integer, default=0)  # number of chunks retrieved
    response_length = Column(Integer, default=0)  # chars in LLM response
    latency_ms = Column(Float, default=0.0)
    collection = Column(String(128), default="Default", nullable=False)
