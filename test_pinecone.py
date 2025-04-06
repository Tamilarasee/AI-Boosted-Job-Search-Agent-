
from utils.pinecone.vector_db import index as pinecone_index

query_1 = "Full-time Machine Learning Engineer jobs in United States with a focus on Machine Learning, Computer Vision, Python, Deep Learning, SQL, and LLMs."

def search_pinecone_jobs(query: str, top_k: int = 10):
    """Search for jobs in Pinecone using the optimized query"""

        # Using Pinecone's correct query format
    results = pinecone_index.search(
            namespace="job-list",
            query={
                "inputs": {"text": query},
                "top_k": top_k
            },
            fields=["_id","_score"]  
        )

    return results
        
results = search_pinecone_jobs(query_1, 5)

print(results)



