from fastapi import HTTPException
from typing import List, Dict
import logging
import sys
from utils.supabase.db import supabase
from dotenv import load_dotenv

load_dotenv()

# Configure logger
logger = logging.getLogger("pinecone_search")
logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


async def fetch_job_details_from_supabase(pinecone_results) -> List[dict]:
    """Fetch full job details from Supabase using IDs from Pinecone results"""
    try:
        # Extract job IDs from Pinecone results, removing 'job_' prefix
        job_ids = [
            int(hit['_id'].replace('job_', '')) 
            for hit in pinecone_results['result']['hits']
        ]
        
        if not job_ids:
            return []
            
        # Fetch full job details from Supabase
        job_details = supabase.table("filtered_jobs")\
            .select("*")\
            .in_("id", job_ids)\
            .execute()
            
        # Create a mapping of job_id to full details for preserving Pinecone's ranking order
        job_map = {job['id']: job for job in job_details.data}
        
        # Return jobs in the same order as Pinecone results, including the similarity score
        ordered_jobs = [
            {
                **job_map[int(hit['_id'].replace('job_', ''))],
                'similarity_score': hit['_score']  # Include the similarity score from Pinecone
            }
            for hit in pinecone_results['result']['hits']
            if int(hit['_id'].replace('job_', '')) in job_map
        ]
        
        return ordered_jobs
        
    except Exception as e:
        logger.error(f"Error fetching job details from Supabase: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch complete job details"
        )

async def fetch_all_supabase_filtered_jobs() -> List[Dict]:
    """Fetches all records from the filtered_jobs table in Supabase."""
    logger = logging.getLogger(__name__) # Use local logger
    logger.info("Fetching all jobs from Supabase filtered_jobs table...")
    try:
        result = supabase.table("filtered_jobs").select("*").execute()
        if result.data:
            logger.info(f"Successfully fetched {len(result.data)} jobs from Supabase.")
            return result.data
        else:
            logger.info("No jobs found in Supabase filtered_jobs table.")
            return []
    except Exception as e:
        logger.error(f"Error fetching all jobs from Supabase: {str(e)}")
        # Depending on desired behavior, you might raise or return empty
        # Raising might be safer to signal a failure in the sync process
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch jobs from Supabase for syncing: {str(e)}"
        )

async def fetch_user_profile(user_id: str) -> str:
    """Fetches the latest resume text for a given user ID from Supabase."""
    logger = logging.getLogger(__name__)
    logger.info(f"Fetching latest resume profile for user_id: {user_id}")
    try:
        # Fetch the latest record for the user based on 'id' (descending)
        user_data_result = supabase.table("users")\
            .select("resumes")\
            .eq("user_id", user_id)\
            .order("id", desc=True)\
            .limit(1)\
            .execute()

        if not user_data_result.data or not user_data_result.data[0].get("resumes"):
            logger.error(f"No resume data found for user: {user_id}")
            raise HTTPException(
                status_code=404, # Not Found might be more appropriate
                detail="No resume found for user. Please ensure a resume is uploaded."
            )

        # Concatenate all resume texts if multiple were uploaded in the latest record
        resume_text = " ".join(user_data_result.data[0]["resumes"])
        logger.info(f"Successfully fetched resume text (length: {len(resume_text)}) for user: {user_id}")
        return resume_text

    except HTTPException as he:
        # Re-raise specific HTTP exceptions
        raise he
    except Exception as e:
        logger.error(f"Error fetching resume for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while fetching resume data for user {user_id}"
        )
