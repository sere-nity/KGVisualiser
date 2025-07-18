import csv
import io
import openai
import os
import pdfplumber
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from database import Base, engine, SessionLocal
from models import CSVUpload, CSVRecord, PDFUpload
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from datetime import datetime
from dotenv import load_dotenv



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
        # extract text from PDF 
        with pdfplumber.open(io.BytesIO(file.file.read())) as pdf:
            all_text = "\n\n".join(
                page.extract_text() or "" for page in pdf.pages
            ).strip()
        
        if not all_text.strip():
            raise HTTPException(status_code=400, detail="No text found in the PDF")
        
        # save content + upload metadata to PDFUpload table
        pdf_upload = PDFUpload(
            filename=file.filename,
            content=all_text,
            created_at=datetime.now()
        )
        db.add(pdf_upload)
        db.commit()
        db.refresh(pdf_upload)

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

        # Retrieve the PDF upload content
        pdf_upload = db.query(PDFUpload).filter(PDFUpload.id == upload_id).first()
        if not pdf_upload:
            raise HTTPException(status_code=404, detail="No PDF found for this upload_id")

        # Use the extracted text as context (limit to first 2000 characters for prompt size)
        context = pdf_upload.content[:2000]

        prompt = f"""User question: {question}

Relevant data from the uploaded PDF:
{context}

Answer:"""

        openai.api_key = os.getenv("OPENAI_API_KEY")
        if not openai.api_key:
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")

        response = openai.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500
        )
        print("response", response)

        answer = response.choices[0].message.content

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
async def chat(request: Request, db: Session = Depends(get_db)):
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
        context_rows = [str(r.row_data) for r in records[:10]]
        context = "\n".join(context_rows)
        
        # 3. Build prompt for the LLM
        prompt = f"""User question: {question}

Relevant data from the uploaded CSV:
{context}

Please answer the user's question based on the data provided above. If the data doesn't contain enough information to answer the question, please say so.

Answer:"""
        
        openai.api_key = os.getenv("OPENAI_API_KEY")
        
        if not openai.api_key:
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")
        
        response = openai.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500
        )
        print("response", response) 
        
        answer = response.choices[0].message.content
        
        return {
            "answer": answer,
            "context_used": context_rows,
            "total_rows": len(records)
        }
        
    except Exception as e:
        print("OpenAI error:", e)
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")




