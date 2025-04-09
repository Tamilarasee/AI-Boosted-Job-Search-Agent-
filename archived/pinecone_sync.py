from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from fastapi import APIRouter, HTTPException
from utils.supabase.db import supabase
import uuid
from datetime import datetime
from utils.pinecone.vector_db import index as pinecone_index
import logging

# Configure logger
logger = logging.getLogger("pinecone_sync")

# Define a Pydantic model for filtered jobs
class FilteredJob(BaseModel):
    id: int  # Supabase record ID
    search_id: int  # The ID of the search that found this job
    title: str
    company: str
    location: Optional[str] = ""
    description: str  # This will be converted to vector embedding
    url: Optional[str] = ""
    date_posted: Optional[str] = ""
    job_type: Optional[str] = ""
    skills_matched: Optional[str] = ""
    total_skills: Optional[int] = 0
    created_at:Optional[datetime] = None

# Create router for Pinecone sync endpoint
router = APIRouter()

@router.post("/sync-pinecone")
async def sync_jobs_to_pinecone():
    """Sync filtered jobs from Supabase to Pinecone"""
    try:
        # Fetch all filtered jobs from Supabase
        result = supabase.table("filtered_jobs").select("*").execute()
        
        if not result.data:
            return {"status": "success", "message": "No jobs found to sync", "count": 0}
            
        # Convert the results to FilteredJob models
        filtered_jobs = [FilteredJob(**job) for job in result.data]
        
        # Prepare records for Pinecone
        records = []
        for job in filtered_jobs:
            
            # Create a unique ID for Pinecone using the job's Supabase ID
            pinecone_id = f"job_{job.id}"
            
            # Prepare the record with the job description as text to be vectorized
            record = {
                "id": pinecone_id,
                "text": job.description,                
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "url": job.url,
                "job_type": job.job_type,
                "date_posted": job.date_posted,
                "skills_matched": job.skills_matched
                
            }
            records.append(record)
        
        # Upsert the records to Pinecone in the "job-listings" namespace
        try:
            # Perform the upsert operation
            response = pinecone_index.upsert_records(
                namespace="job-list",
                records=records
            )
            
            return {
                "status": "success",
                "message": f"Successfully synced {len(filtered_jobs)} jobs to Pinecone",
                "pinecone_response": response,
                "count": len(filtered_jobs)
            }
        except Exception as e:
            # Log the error and return a detailed error message
            logger.error(f"Error upserting to Pinecone: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error upserting jobs to Pinecone: {str(e)}"
            )
    except Exception as e:
        logger.error(f"Error in sync process: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error syncing jobs to Pinecone: {str(e)}"
        )
