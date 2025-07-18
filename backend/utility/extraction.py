import openai
import os
import pdfplumber
import io
from llama_index.core.indices.knowledge_graph import KnowledgeGraphIndex
from llama_index.llms.openai import OpenAI
from llama_index.core.storage.storage_context import StorageContext
from llama_index.core.graph_stores.simple import SimpleGraphStore
from models import PDFUpload, KnowledgeGraphTriplet
from sqlalchemy.orm import Session
from llama_index.core import Document
from dotenv import load_dotenv
from llama_index.core.settings import Settings
load_dotenv()

key = os.getenv("OPENAI_API_KEY")
if key:
    os.environ["OPENAI_API_KEY"] = key

# Set global LLM and chunk size
Settings.llm = OpenAI(model="gpt-4.1-nano", temperature=0)
Settings.chunk_size = 512  # or whatever chunk size you want

def extract_triplets_from_pdf(pdf_upload: PDFUpload, db: Session):
    print("Starting triplet extraction for PDF:", pdf_upload.id)

    text = getattr(pdf_upload, "content", None)
    if not text or not isinstance(text, str):
        print("No text found in PDF upload.")
        return

    documents = [Document(text=text)]
    print("Document created, length:", len(text))

    graph_store = SimpleGraphStore()
    storage_context = StorageContext.from_defaults(graph_store=graph_store)

    kg_index = KnowledgeGraphIndex.from_documents(
        documents=documents,
        storage_context=storage_context,
        max_triplets_per_chunk=5,
        include_embeddings=False
    )

    print("KnowledgeGraphIndex built.")

    print("Calling get_networkx_graph()")
    graph = kg_index.get_networkx_graph()
    print("Graph obtained:", graph)
    triplets = []
    for u, v, data in graph.edges(data=True):
        print(f"Edge: {u} -> {v}, data: {data}")
        rel = data.get('relation') or data.get('label') or data.get('title')
        if rel is not None:
            triplets.append((u, rel, v))
        else:
            print(f"Skipping edge {u}->{v} with missing relation/label/title: {data}")
    print("Extracted triplets:", triplets)

    for head, rel, tail in triplets:
        triplet = KnowledgeGraphTriplet(
            pdf_upload_id=pdf_upload.id,
            subject=head.strip(),
            relation=rel.strip(),
            object=tail.strip(),
            source_text=None
        )
        db.add(triplet)

    db.commit()
    print("Triplets committed to DB.")
    


# Extract text from a PDF file (UploadFile)
def extract_text_from_pdf(upload_file):
    with pdfplumber.open(io.BytesIO(upload_file.file.read())) as pdf:
        all_text = "\n\n".join(
            page.extract_text() or "" for page in pdf.pages
        ).strip()
    return all_text



# Extract context from CSV records (limit to first 10 rows)
def extract_context_from_csv_records(records):
    context_rows = [str(r.row_data) for r in records[:10]]
    return "\n".join(context_rows)