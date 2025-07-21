from llama_index.core.llms import LLM 
import numpy as np
from models import NodeEmbedding

def cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def get_similar_pairs(pdf_upload_id, db, similarity_threshold=0.5, max_pairs=1000):
    """Generate candidate node pairs for cross-node relationship extraction, 
       based on some similarity threshold. Cuz it's too computationally expensive to compare all pairs. 
    """
    node_embeddings = db.query(NodeEmbedding).filter_by(pdf_upload_id=pdf_upload_id).all()
    print(f"[get_similar_pairs] Number of node embeddings: {len(node_embeddings)}")

    scored_pairs = []
    
    # compare each embedding to every other embedding
    for i in range(len(node_embeddings)):
        for j in range(i+1, len(node_embeddings)):
            ne1 = node_embeddings[i]
            ne2 = node_embeddings[j]
            similarity = cosine_similarity(ne1.embedding, ne2.embedding)
            print(f"[get_similar_pairs] Similarity between {ne1.node_id} and {ne2.node_id}: {similarity}")
            if similarity > similarity_threshold:
                scored_pairs.append((similarity, (ne1.node_id, ne2.node_id)))
    
    # sort pairs by similarity, highest first (most similar first)
    scored_pairs.sort(reverse=True)
    print(f"[get_similar_pairs] Number of pairs above threshold: {len(scored_pairs)}")
    # return top max_pairs pairs
    result = [pair for _, pair in scored_pairs[:max_pairs]]
    print(f"[get_similar_pairs] Returning {len(result)} pairs (max_pairs={max_pairs})")
    return result

