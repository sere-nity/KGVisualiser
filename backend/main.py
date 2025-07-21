import csv
import io
import openai
import os
import pdfplumber
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from database import Base, engine, SessionLocal
from models import CSVUpload, CSVRecord, PDFUpload, KnowledgeGraphTriplet, NodeEmbedding
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from datetime import datetime
from dotenv import load_dotenv
from utility.extraction import extract_text_from_pdf, process_pdf_to_kg, extract_context_from_csv_records
from utility.llm import chat_with_llm

load_dotenv()

# ensure tables get created on startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # TODO - change to only allow requests from the frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# dependency for DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ENDPOINTS --------------------------------------------------------------------

@app.get("/")
def read_root():
    return {"Hello": "World"}

# has to be synchronous
@app.post("/upload-csv")
def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # process CSV 
    try:
        contents = file.file.read().decode("utf-8")  # decode into string from bytes
        csv_reader = csv.DictReader(io.StringIO(contents)) # io.StringIO - in-memory buffer
        # save upload metadata to CSVUpload table
        csv_upload = CSVUpload(
            filename=file.filename, #Nt - id column is auto-populated
            created_at=datetime.now()
        )
        db.add(csv_upload)
        db.commit()
        # refresh to get the auto-generated id for the next table
        db.refresh(csv_upload)

        # bulk insert each row to CSVRecord table
        records = []
        for row in csv_reader:
            csv_record = CSVRecord(
                upload_id=csv_upload.id,
                row_data=row,
                created_at=datetime.now()
            )
            records.append(csv_record)
        db.add_all(records)
        db.commit()
        return {"message": "CSV uploaded successfully", "upload_id": csv_upload.id}
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"CSV upload failed: {e}")


# PDF ENDPOINT ----------------------------------------------------------------

@app.post("/upload-pdf")
def upload_pdf(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        # 1. Extract text from PDF using utility
        all_text = extract_text_from_pdf(file)
        if not all_text.strip():
            raise HTTPException(status_code=400, detail="No text found in the PDF")
        # 2. Save content + upload metadata to PDFUpload table
        pdf_upload = PDFUpload(
            filename=file.filename,
            content=all_text,
            created_at=datetime.now()
        )
        db.add(pdf_upload)
        db.commit()
        db.refresh(pdf_upload)

        # 3. Extract triplets from the PDF
        process_pdf_to_kg(pdf_upload, db)

        return {"message": "PDF uploaded successfully", "upload_id": pdf_upload.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"PDF upload failed: {e}\n")



@app.post("/chat-pdf")
async def chat_pdf(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        question = data.get("question")
        upload_id = data.get("upload_id")
        if not question or not upload_id:
            raise HTTPException(status_code=400, detail="Missing question or upload_id")
        # 1. Retrieve the PDF upload content from the database
        pdf_upload = db.query(PDFUpload).filter(PDFUpload.id == upload_id).first()
        if not pdf_upload:
            raise HTTPException(status_code=404, detail="No PDF found for this upload_id")
        # 2. Use the extracted text as context (limit to first 2000 characters for prompt size)
        context = pdf_upload.content[:2000]
        # 3. Call shared LLM chat utility
        answer = chat_with_llm(question, context, context_type="PDF")
        return {
            "answer": answer,
            "context_used": context,
            "upload_id": upload_id
        }
    except Exception as e:
        print("OpenAI error:", e)
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

# OLD CSV ENDPOINT ------------------------------------------------------------
@app.post("/chat-csv")
async def chat_csv(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        question = data.get("question")
        upload_id = data.get("upload_id")
        if not question or not upload_id:
            raise HTTPException(status_code=400, detail="Missing question or upload_id")
        # 1. Retrieve relevant rows from the database
        records = db.query(CSVRecord).filter(CSVRecord.upload_id == upload_id).all()
        if not records:
            raise HTTPException(status_code=404, detail="No data found for this upload_id")
        # 2. Build context from the data (limit to first 10 rows to avoid token limits)
        context = extract_context_from_csv_records(records)
        # 3. Call shared LLM chat utility
        answer = chat_with_llm(question, context, context_type="CSV")
        return {
            "answer": answer,
            "context_used": context,
            "total_rows": len(records)
        }
    except Exception as e:
        print("OpenAI error:", e)
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

# ENDPOINT FOR GETTING RELATIONSHIP DATA ----------------------------------
# Called after PDF uploaded 
@app.get("/graph/{pdf_id}")
def get_knowledge_graph(pdf_id: int, db: Session = Depends(get_db)):
    triplets = db.query(KnowledgeGraphTriplet).filter(
        KnowledgeGraphTriplet.pdf_upload_id == pdf_id
    ).all()
    # Return as a list of dicts for frontend
    return [
        {
            "subject": t.subject,
            "relation": t.relation,
            "object": t.object,
            "source_text": t.source_text,
        }
        for t in triplets
    ]

# ENDPOINT FOR GETTING NODE CLUSER ID DATA ----------------------------------
@app.get("/graph/nodes/{pdf_id}")
def get_node_embeddings(pdf_id: int, db: Session = Depends(get_db)):
    node_embeddings = db.query(NodeEmbedding).filter(
        NodeEmbedding.pdf_upload_id == pdf_id
    ).all()
    return [
        {
            "node_id": ne.node_id,
            "cluster_id": ne.cluster_id,
        }
        for ne in node_embeddings
    ]
