from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from database import Base

class CSVUpload(Base):
    __tablename__ = "csv_uploads"
    id = Column(Integer, primary_key=True)
    filename = Column(String)
    created_at = Column(DateTime, default=datetime.now)

class CSVRecord(Base):
    __tablename__ = "csv_records"
    id = Column(Integer, primary_key=True)
    upload_id = Column(Integer, ForeignKey("csv_uploads.id"))
    row_data = Column(JSONB)
    created_at = Column(DateTime, default=datetime.now)