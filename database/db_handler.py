import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

from config import DATABASE_URL

Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class DownloadRequest(Base):
    __tablename__ = "download_requests"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, index=True)
    user_id = Column(Integer, index=True)
    url = Column(String(255))
    tracks = Column(String(255), nullable=True)
    status = Column(String(50), default="queued")  # queued, processing, completed, failed
    download_type = Column(String(20))  # album, select
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    download_path = Column(String(255), nullable=True)
    gofile_url = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    message_id = Column(Integer, nullable=True)

@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)

def add_download_request(chat_id, user_id, url, download_type, tracks=None, message_id=None):
    with get_db() as db:
        download_request = DownloadRequest(
            chat_id=chat_id,
            user_id=user_id,
            url=url,
            tracks=tracks,
            download_type=download_type,
            message_id=message_id
        )
        db.add(download_request)
        db.commit()
        db.refresh(download_request)
        return download_request.id

def get_request_by_id(request_id):
    with get_db() as db:
        return db.query(DownloadRequest).filter(DownloadRequest.id == request_id).first()

def update_request_status(request_id, status, **kwargs):
    with get_db() as db:
        request = db.query(DownloadRequest).filter(DownloadRequest.id == request_id).first()
        if request:
            request.status = status
            for key, value in kwargs.items():
                if hasattr(request, key):
                    setattr(request, key, value)
            db.commit()
            return True
        return False

def get_requests_in_queue():
    with get_db() as db:
        return db.query(DownloadRequest).filter(
            DownloadRequest.status == "queued",
            DownloadRequest.is_active == True
        ).order_by(DownloadRequest.created_at).all()

def get_active_processing_count():
    with get_db() as db:
        return db.query(DownloadRequest).filter(
            DownloadRequest.status == "processing",
            DownloadRequest.is_active == True
        ).count()

def cancel_request(request_id):
    with get_db() as db:
        request = db.query(DownloadRequest).filter(DownloadRequest.id == request_id).first()
        if request and request.status in ["queued", "processing"]:
            request.status = "cancelled"
            request.is_active = False
            db.commit()
            return True
        return False

def get_user_active_requests(user_id):
    with get_db() as db:
        return db.query(DownloadRequest).filter(
            DownloadRequest.user_id == user_id,
            DownloadRequest.is_active == True
        ).all()

def set_message_id(request_id, message_id):
    with get_db() as db:
        request = db.query(DownloadRequest).filter(DownloadRequest.id == request_id).first()
        if request:
            request.message_id = message_id
            db.commit()
            return True
        return False