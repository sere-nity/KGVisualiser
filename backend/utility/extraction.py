import openai
import os
import pdfplumber
import io
from llama_index.core.indices.knowledge_graph import KnowledgeGraphIndex
from llama_index.llms.openai import OpenAI
from llama_index.core.storage.storage_context import StorageContext
from llama_index.core.graph_stores.simple import SimpleGraphStore
from models import PDFUpload, KnowledgeGraphTriplet, NodeEmbedding
from sqlalchemy.orm import Session
from llama_index.core import Document
from dotenv import load_dotenv
from llama_index.core.settings import Settings
from llama_index.embeddings.openai import OpenAIEmbedding
from datetime import datetime
import numpy as np
from llama_index.core.prompts import PromptTemplate, PromptType

load_dotenv()

key = os.getenv("OPENAI_API_KEY")
if key:
    os.environ["OPENAI_API_KEY"] = key

# Set global LLM and chunk size
Settings.llm = OpenAI(model="gpt-3.5-turbo", temperature=0)
Settings.chunk_size = 512  
Settings.embed_model = OpenAIEmbedding(embed_batch_size=10)

CUSTOM_KG_TRIPLET_EXTRACT_TMPL = (
    "Some text is provided below. Given the text, extract up to "
    "{max_knowledge_triplets} "
    "knowledge triplets in the form of (subject, predicate, object). Avoid stopwords.\n"
    "---------------------\n"
    "Example (do NOT include in your output):\n"
    "Text: Alice is Bob's mother.\n"
    "Triplets:\n(Alice, is mother of, Bob)\n"
    "Text: Philz is a coffee shop founded in Berkeley in 1982.\n"
    "Triplets:\n"
    "DO NOT INCLUDE THIS IN THE OUTPUT!\n"
    "(Philz, is, coffee shop)\n"
    "DO NOT INCLUDE THIS IN THE OUTPUT!\n"
    "(Philz, founded in, Berkeley)\n"
    "DO NOT INCLUDE THIS IN THE OUTPUT!\n"
    "(Philz, founded in, 1982)\n"
    "---------------------\n"
    "Text: {text}\n"
    "Triplets:\n"
)
custom_prompt = PromptTemplate(
    CUSTOM_KG_TRIPLET_EXTRACT_TMPL,
    prompt_type=PromptType.KNOWLEDGE_TRIPLET_EXTRACT
)

def extract_triplets_from_pdf(pdf_upload: PDFUpload, db: Session):
    text = get_pdf_text(pdf_upload)
    if not text:
        print("No text found in PDF upload.")
        return
    kg_index = build_kg_index(text)
    extract_and_store_triplets(kg_index, pdf_upload, db)
    store_node_embeddings(kg_index, pdf_upload, db)
    assign_node_embedding_clusters(pdf_upload.id, db)

def get_pdf_text(pdf_upload: PDFUpload):
    text = getattr(pdf_upload, "content", None)
    if not text or not isinstance(text, str):
        return None
    return text

def build_kg_index(text: str):
    documents = [Document(text=text)]
    graph_store = SimpleGraphStore()
    storage_context = StorageContext.from_defaults(graph_store=graph_store)
    kg_index = KnowledgeGraphIndex.from_documents(
        documents=documents,
        storage_context=storage_context,
        max_triplets_per_chunk=5,
        include_embeddings=False,
        kg_triple_extract_template=custom_prompt
    )
    print("KnowledgeGraphIndex built.")
    return kg_index

def extract_and_store_triplets(kg_index, pdf_upload, db):
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

def store_node_embeddings(kg_index, pdf_upload, db):
    # use global embed model 
    embed_model = Settings.embed_model
    graph = kg_index.get_networkx_graph()
    for node_name in graph.nodes():
        embedding = embed_model.get_text_embedding(node_name)
        embedding = list(embedding)
        node_embedding = NodeEmbedding(
            pdf_upload_id=pdf_upload.id,
            node_id=node_name,
            embedding=embedding,
            cluster_id=None,
            created_at=datetime.now()
        )
        db.add(node_embedding)
    db.commit()

def assign_node_embedding_clusters(pdf_upload_id, db, n_clusters=4):
    """ 
    Assign cluster IDs to node embeddings in the db. 
    """
    from sklearn.cluster import KMeans
    # get node embeddings ref. by pdf_upload_id from db 
    node_embeddings = db.query(NodeEmbedding).filter_by(pdf_upload_id=pdf_upload_id).all()

    # just extract the embedding field from node_embeddings
    embeddings = [ne.embedding for ne in node_embeddings]

    # convert embeddings to numpy array
    X = np.array(embeddings, dtype=float)

    # fit kmeans model
    kmeans = KMeans(n_clusters=n_clusters).fit(X)

    # get cluster assignment
    labels = kmeans.labels_

    # deal with case where assignment is None
    if labels is None:
        print("Clustering failed: labels_ is None")
        return
    labels = np.array(labels).flatten()
    # assign cluster labels to node_embeddings
    for node_embedding, cluster_id in zip(node_embeddings, labels):
        node_embedding.cluster_id = int(cluster_id)
        # (no need to add node_embedding to db, it's already in the db) ??? 
    db.commit()
    print(f"Cluster IDs assigned and committed to DB for PDF upload {pdf_upload_id}.")


def extract_text_from_pdf(upload_file):
    """
    Extract text from a PDF file (UploadFile). 
    Note there will be two new lines between each page. 
    """
    with pdfplumber.open(io.BytesIO(upload_file.file.read())) as pdf:
        all_text = "\n\n".join(
            page.extract_text() or "" for page in pdf.pages
        ).strip()
    return all_text

def extract_context_from_csv_records(records):
    """
    Extract context from CSV records (limit to first 10 rows).
    LEGACY FUNCTION
    """
    context_rows = [str(r.row_data) for r in records[:10]]
    return "\n".join(context_rows)