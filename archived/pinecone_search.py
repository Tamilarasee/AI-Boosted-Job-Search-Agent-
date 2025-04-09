from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import logging
import sys
from utils.supabase.db import supabase
from litellm import acompletion
from dotenv import load_dotenv
from utils.pinecone.vector_db import index as pinecone_index
import asyncio
from api.analysis import analyze_job_fit_and_provide_tips
from utils.pinecone.pinecone_utils import generate_optimized_query, search_pinecone_jobs
from utils.supabase.supabase_utils import fetch_job_details_from_supabase

load_dotenv()

# Configure logger
logger = logging.getLogger("pinecone_search")
logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Define request model for Pinecone search
class PineconeSearchRequest(BaseModel):
    user_id: str
    target_roles: str
    primary_skills: Optional[str] = ""
    preferred_location: Optional[str] = ""
    job_type: Optional[list[str]] = ["Full-time"]
    additional_preferences: Optional[str] = ""

# Create router
router = APIRouter()



@router.post("/search-pinecone")
async def search_pinecone_endpoint(request: PineconeSearchRequest):
    logger.info(f"Received Pinecone search request for user: {request.user_id}")
    
    # 1. Fetch latest resume from Supabase using request.user_id
    try:
        user_data_result = supabase.table("users")\
            .select("resumes")\
            .eq("user_id", request.user_id)\
            .order("id", desc=True).limit(1)\
            .execute()
            
        if not user_data_result.data or not user_data_result.data[0].get("resumes"):
            raise HTTPException(
                status_code=400,
                detail="No resume found for user. Please ensure a resume is uploaded."
            )
            
        resume_text = " ".join(user_data_result.data[0]["resumes"])
        print("\nResume text: ", resume_text)
        logger.info(f"Successfully fetched latest resume text for user: {request.user_id}")
            
    except Exception as e:
        logger.error(f"Error fetching resume: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while fetching resume data"
        )
    
    # 2. Combine resume + preferences from request

    search_context = {
        "resume_text": resume_text,
        "target_roles": request.target_roles,
        "primary_skills": request.primary_skills,
        "location": request.preferred_location,
        "job_type": request.job_type,
        "additional_preferences": request.additional_preferences
    }

    # Use LiteLLM to generate an optimized search query

    optimized_query = await generate_optimized_query(search_context)
    logger.info(f"Generated optimized query: {optimized_query}")
    
    # Search Pinecone
    pinecone_results = await search_pinecone_jobs(optimized_query)
    
    # Fetch full job details and format for UI
    complete_job_results = await fetch_job_details_from_supabase(pinecone_results)
    
    # --- Step 1 & 4: Prepare and run analysis concurrently ---
    top_jobs_for_analysis = complete_job_results[:5] # Analyze top 5 jobs
    analysis_tasks = []
    job_ids_for_analysis = [] # Keep track of IDs for merging later

    logger.info(f"Starting analysis for top {len(top_jobs_for_analysis)} jobs...")
    for job in top_jobs_for_analysis:
        # Ensure job has an ID and description before creating task
        if job.get('id') and job.get('description'):
             task = asyncio.create_task(
                 analyze_job_fit_and_provide_tips(resume_text, job)
             )
             analysis_tasks.append(task)
             job_ids_for_analysis.append(job['id']) # Store ID corresponding to task order
        else:
            logger.warning(f"Skipping analysis for job due to missing ID or description: {job.get('title', 'N/A')}")

    # Run tasks concurrently and wait for all to complete
    analysis_outputs = []
    if analysis_tasks:
        try:
             # Wait for all analysis tasks to complete
             analysis_outputs = await asyncio.gather(*analysis_tasks)
             logger.info(f"Completed analysis for {len(analysis_outputs)} jobs.")
        except Exception as e:
            logger.error(f"Error during concurrent job analysis: {str(e)}")
            # analysis_outputs will remain empty or partially filled; proceed gracefully

    # --- Step 5: Integrate Results ---
    # Create a map of job_id -> analysis_result
    analysis_map = {
        job_id: result 
        for job_id, result in zip(job_ids_for_analysis, analysis_outputs) 
        if result # Only include successful analyses (non-empty dicts)
    }

    # --- Format results for UI (Now including analysis) ---
    formatted_results = []
    for job in complete_job_results:
        job_id = job.get('id')
        analysis_data = analysis_map.get(job_id, {}) # Get analysis if available, else empty dict
        
        formatted_results.append({
            **job,
            'match_percentage': round(job.get('similarity_score', 0) * 100, 1), # Added .get for safety
            'match_text': f"{round(job.get('similarity_score', 0) * 100)}% Match",
            'analysis': analysis_data # Add the analysis results here
        })

    logger.info(f"Returning {len(formatted_results)} results to UI.")
    logger.info(f"Formatted results: {formatted_results[0]}")
    return {
        "status": "success",
        "query": optimized_query,
        "results": formatted_results, # Now includes analysis results
        "total_results": len(formatted_results)
    }

