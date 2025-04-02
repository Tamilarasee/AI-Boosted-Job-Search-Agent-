from pinecone import Pinecone
from dotenv import load_dotenv
import os

load_dotenv()

pc = Pinecone(api_key = os.getenv("PINECONE_API_KEY"))
print(os.getenv("PINECONE_API_KEY"))
# Create index if it doesn't exist

index = pc.Index("job-search-tool")









