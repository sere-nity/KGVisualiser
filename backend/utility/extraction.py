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
from sqlalchemy import and_
from llama_index.core import Document
from dotenv import load_dotenv
from llama_index.core.settings import Settings
from llama_index.embeddings.openai import OpenAIEmbedding
from datetime import datetime
import numpy as np
from llama_index.core.prompts import PromptTemplate, PromptType
from utility.pairs import get_similar_pairs
import re

# ALL FUNCTIONS TO DO WITH EXTRACTING AND PROCESSING TEXT FROM PDFS

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

SIMILARITY_THRESHOLD = 0.8
MAX_PAIRS = 1000

def process_pdf_to_kg(pdf_upload: PDFUpload, db: Session):
    """
    Orchestrate the full pipeline: extract text, build KG, store triplets, embeddings, clusters.
    """
    text = get_pdf_text(pdf_upload)
    if not text:
        print("No text found in PDF upload.")
        return
    kg_index = build_kg_index(text)
    triplets = extract_chunk_triplets(kg_index)
    store_triplets(triplets, pdf_upload, db)
    store_node_embeddings(kg_index, pdf_upload, db)
    assign_node_embedding_clusters(pdf_upload.id, db)
    # second-pass global relationship extraction
    extract_cross_node_relationships(pdf_upload.id, db, SIMILARITY_THRESHOLD, MAX_PAIRS)
    remove_specific_nodes(pdf_upload.id, db)

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

def extract_chunk_triplets(kg_index):
    """
    Extract triplets from the KG index (chunk-based, first pass).
    Returns a list of (subject, relation, object) tuples.
    """
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
    return triplets

def store_triplets(triplets, pdf_upload, db):
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

# ---------------------------------------------------------------------

def extract_cross_node_relationships(pdf_upload_id, db, similarity_threshold, max_pairs, batch_size=10, max_new_triplets_per_batch=20):
    """
    For each candidate node pair, prompt the LLM for a possible relationship, batching pairs for efficiency.
    Includes the PDF content as context in the prompt.
    """
    llm = Settings.llm
    similar_pairs = get_similar_pairs(pdf_upload_id, db, similarity_threshold, max_pairs)
    print(f"Found {len(similar_pairs)} similar pairs.")

    # Fetch PDF content from the database for context
    pdf_upload = db.query(PDFUpload).filter(PDFUpload.id == pdf_upload_id).first()
    if not pdf_upload:
        print(f"No PDF found for id {pdf_upload_id}, skipping cross-node extraction.")
        return
    pdf_context = pdf_upload.content[:2000]  # Use first 2000 chars as context

    TRIPLET_REGEX = re.compile(r"\(\s*['\"]?([^,]+?)['\"]?\s*,\s*['\"]?([^,]+?)['\"]?\s*,\s*['\"]?([^,]+?)['\"]?\s*\)")

    def parse_triplet(line):
        match = TRIPLET_REGEX.match(line)
        if match:
            return tuple(part.strip().strip('"\'') for part in match.groups())
        if ',' in line:
            parts = [p.strip().strip('"\'') for p in line.split(',')]
            if len(parts) == 3:
                return tuple(parts)
        return None

    def batch(iterable, n=1):
        l = len(iterable)
        for ndx in range(0, l, n):
            yield iterable[ndx:min(ndx + n, l)]

    for pair_batch in batch(similar_pairs, batch_size):
        pairs_str = "\n".join([f"- {a}, {b}" for a, b in pair_batch])
        prompt = (
            f"Document context:\n{pdf_context}\n"
            "Given the following entity pairs, extract any relationships using the provided context as (subject, predicate, object) triplets. "
            "The predicate should be a short phrase describing the relationship (e.g., 'uses', 'created by', 'is part of'). "
            "Do NOT return full sentences. Only return triplets in the format: (subject, predicate, object).\n"
            "Example:\n"
            "Pair: Alice, Bob\n"
            "Triplet: (Alice, is friend of, Bob)\n"
            "Pair: Paris, France\n"
            "Triplet: (Paris, is capital of, France)\n"
            "If no relationship exists, omit the pair.\n"
            f"Pairs:\n{pairs_str}"
        )
        response = llm.complete(prompt).text.strip()
        print(f"LLM Batch Response:\n{response}")
        # Parse the LLM's response for triplets
        lines = [line.strip() for line in response.splitlines() if line.strip()]
        added_count = 0
        for line in lines:
            # Remove leading list markers and whitespace
            line = line.lstrip("-•* \t").strip()
            if line.lower() == "none":
                continue
            triplet = parse_triplet(line)
            if not triplet or not all(triplet):
                print(f"Skipped malformed or incomplete triplet: {line}")
                continue
            # Normalize for duplicate check
            triplet_norm = tuple(x.strip().lower() for x in triplet)
            exists = db.query(KnowledgeGraphTriplet).filter(
                and_(
                    KnowledgeGraphTriplet.pdf_upload_id == pdf_upload_id,
                    KnowledgeGraphTriplet.subject.ilike(triplet_norm[0]),
                    KnowledgeGraphTriplet.relation.ilike(triplet_norm[1]),
                    KnowledgeGraphTriplet.object.ilike(triplet_norm[2]),
                )
            ).first()
            if not exists:
                db.add(KnowledgeGraphTriplet(
                    pdf_upload_id=pdf_upload_id,
                    subject=triplet[0],
                    relation=triplet[1],
                    object=triplet[2],
                    source_text=None
                ))
                db.commit()
                added_count += 1
                print(f"Added new cross-node triplet: {triplet}")
            if added_count >= max_new_triplets_per_batch:
                print(f"Reached max new triplets ({max_new_triplets_per_batch}) for this batch.")
                break



# ---------------------------------------------------------------------

def remove_specific_nodes(pdf_upload_id, db, keywords=None):
    """
    This is hard-coded. Couldn't figure out how to remove the default stuff :( 
    """
    if keywords is None:
        keywords = ["Berkeley", "Philz", "1982"]
    # Case-insensitive search
    for kw in keywords:
        deleted = db.query(KnowledgeGraphTriplet).filter(
            KnowledgeGraphTriplet.pdf_upload_id == pdf_upload_id,
            (
                KnowledgeGraphTriplet.subject.ilike(f"%{kw}%") |
                KnowledgeGraphTriplet.relation.ilike(f"%{kw}%") |
                KnowledgeGraphTriplet.object.ilike(f"%{kw}%")
            )
        ).delete(synchronize_session=False)
        if deleted:
            print(f"Deleted {deleted} triplets containing '{kw}' for PDF {pdf_upload_id}.")
    db.commit()

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


