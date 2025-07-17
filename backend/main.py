from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from database import Base, engine, SessionLocal
from models import CSVUpload, CSVRecord


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # TODO - change to only allow requests from the frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency for DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# endpoints

# Ensure tables get created on startup
@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

@app.get("/")
def read_root():
    return {"Hello": "World"}

# uploading CSV, querying?, AI chat?? 
@app.post("/upload-csv")
def upload_csv(file: UploadFile = File(...)):
    # process CSV 
    return {"message": "CSV uploaded successfully"}

