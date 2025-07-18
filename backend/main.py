import csv
import io
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from database import Base, engine, SessionLocal
from models import CSVUpload, CSVRecord
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from datetime import datetime
import openai
import os
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

# endpoints - uploading CSV, querying?, AI chat?? 

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

@app.post("/chat")
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

