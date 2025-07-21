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

# Stores data abt the RELATIONSHIPS in the knowledge graph. 
class KnowledgeGraphTriplet(Base):
    __tablename__ = "knowledge_graph_triplets"
    id = Column(Integer, primary_key=True)
    pdf_upload_id = Column(Integer, ForeignKey("pdf_uploads.id"))
    subject = Column(Text)
    relation = Column(Text)
    object = Column(Text)
    source_text = Column(Text)  # optional: context triplet came from 
    # node_type = Column(String)  # optional: e.g., "entity", "concept", etc.
    created_at = Column(DateTime, default=datetime.now)

# Stores data abt the NODES in the knowledge graph. 
class NodeEmbedding(Base):
    __tablename__ = "node_embeddings"
    id = Column(Integer, primary_key=True)
    pdf_upload_id = Column(Integer, ForeignKey("pdf_uploads.id"))
    node_id = Column(String)
    embedding = Column(JSONB)  # Store the embedding vector as JSON
    cluster_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)