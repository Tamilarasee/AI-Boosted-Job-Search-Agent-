
from utils.pinecone.vector_db import index as pinecone_index

query_1 = '''

 Based on the provided resume text and job preferences, here's an optimized search query that captures the essential requirements:

```
"Machine Learning Engineer" OR "AI Engineer" AND "Full-time" AND "United States" AND 
("Machine Learning" OR "AI" OR "Artificial Intelligence") AND ("Python" AND ("3 years" OR "3+ years") AND "SQL") AND ("Healthcare IT" OR "Medical") AND ("Computer Vision" OR "Deep Learning") AND ("1 year" OR "1+ years" OR "Project experience") AND ("Flutter" OR "Mobile App") AND -Java -Golang -Javascript -HTML -CSS
```

This query:

- Focuses on target roles in machine learning and AI.
- Specifies key skills: Python, SQL, Machine Learning, AI, Computer Vision, and Deep 
Learning.
- References relevant experience in healthcare IT and aligns with the job seeker's skills and projects.
- Includes filter criteria for full-time roles in the United States.
- Excludes languages and technologies that are not within the candidate's skill set.
'''

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



