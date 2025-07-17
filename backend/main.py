import csv
import io
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from database import Base, engine, SessionLocal
from models import CSVUpload, CSVRecord
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from datetime import datetime


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

