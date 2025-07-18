from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from database import Base

# OLD MODELS FOR CSV ------------------------------------------------
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

# ---------------------------------------------------------------------

class PDFUpload(Base):
    __tablename__ = "pdf_uploads"
    id = Column(Integer, primary_key=True)
    filename = Column(String)
    content = Column(Text)  # Store full PDF text here
    created_at = Column(DateTime, default=datetime.now)


