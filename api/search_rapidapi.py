import os
import json
import requests
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional, Coroutine
from fastapi import APIRouter, BackgroundTasks, HTTPException
from api.filtering import *
from pydantic import BaseModel
import logging
import sys
import uuid
from utils.supabase.db import supabase
from datetime import datetime
import asyncio
from utils.supabase.supabase_utils import (
    fetch_user_profile,
    fetch_all_supabase_filtered_jobs,
    fetch_job_details_from_supabase
)
from utils.pinecone.pinecone_utils import (
    generate_optimized_query,
    delete_pinecone_namespace_vectors,
    sync_jobs_to_pinecone_utility,
    search_pinecone_jobs
)
from api.analysis import analyze_job_fit_and_provide_tips


# Configure logging first
logging.basicConfig(level=logging.INFO, stream=sys.stdout, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("job_search_api")

# Load environment variables
load_dotenv()
#RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_KEY = ""

# Add debug logging for API key
if not RAPIDAPI_KEY:
    logger.error("RAPIDAPI_KEY not found in environment variables!")
else:
    logger.info("RAPIDAPI_KEY loaded successfully")
    # Only log first few characters for security
    logger.info(f"RAPIDAPI_KEY starts with: {RAPIDAPI_KEY[:4]}...")

# Create router for the API endpoints
router = APIRouter()

# Define job search request model
class JobSearchRequest(BaseModel):
    user_id: str
    target_roles: List[str]
    primary_skills: Optional[List[str]] = []
    preferred_location: Optional[str] = ""
    job_type: Optional[str] = "Full-time"
    additional_preferences: Optional[str] = ""
    
    class Config:
        # Make model schema printing more detailed
        schema_extra = {
            "example": {
                "target_roles": ["Software Engineer", "Full Stack Developer"],
                "primary_skills": ["Python", "JavaScript", "React"],
                "preferred_location": "San Francisco, CA",
                "job_type": "Full-time",
                "additional_preferences": "Remote friendly"
            }
        }

# In-memory storage for job results
job_results_store = {}

PINECONE_NAMESPACE = "job-list" 



# --- Block 2: Define Placeholder Helper Function Signatures ---
# We will fill these in later blocks
async def fetch_and_filter_api_jobs(request: JobSearchRequest) -> List[Dict]:
    """Fetches jobs from RapidAPI, processes, and filters them."""
    logger.info("Starting Task 1: Fetch and Filter API Jobs")
    
    # --- API Call Setup ---
    url = "https://linkedin-job-search-api.p.rapidapi.com/active-jb-7d" # Or your chosen API endpoint
    
    # Format filters based on request
    if request.target_roles and len(request.target_roles) > 1:
        title_filter = " OR ".join([f'"{role}"' for role in request.target_roles])
    elif request.target_roles:
        title_filter = f'"{request.target_roles[0]}"'
    else:
         title_filter = "" # Handle case with no roles? Or make mandatory in request model

    location_filter = f'"{request.preferred_location}"' if request.preferred_location else ""
    
    job_type_mapping = {
        "full-time": "FULL_TIME",
        "part-time": "PART_TIME",
        "contract": "CONTRACTOR",
        "internship": "INTERN",
        "temporary": "TEMPORARY",
        "volunteer": "VOLUNTEER"
    }
    # Handle job_type being string or None (adjust based on JobSearchRequest model)
    type_filter = job_type_mapping.get(request.job_type.lower() if request.job_type else "full-time", "FULL_TIME")

    querystring = {
        "limit": "25", # Fetch a reasonable number
        "offset": "0",
        "title_filter": title_filter,
        "location_filter": location_filter,
        "type_filter": type_filter,
        "description_type": "text"
    }
    # Remove empty filters if API requires it
    querystring = {k: v for k, v in querystring.items() if v}

    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY, # Ensure RAPIDAPI_KEY is loaded from .env
        "x-rapidapi-host": "linkedin-job-search-api.p.rapidapi.com"
    }
    
    # --- API Call & Processing ---
    try:
        logger.info(f"Making API request to {url} with query: {querystring}")
        # NOTE: requests.get is synchronous. Using httpx would be truly async.
        # Running sync code within asyncio.to_thread to avoid blocking event loop severely.
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None, # Use default thread pool executor
            lambda: requests.get(url, headers=headers, params=querystring) # Add timeout
        )
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        
        linkedin_jobs_raw = response.json()
        # Add basic check if response is a list as expected
        if not isinstance(linkedin_jobs_raw, list):
             logger.error(f"API response was not a list: {linkedin_jobs_raw}")
             return [] # Return empty list if format is unexpected

        all_jobs = process_linkedin_jobs(linkedin_jobs_raw) # Use existing processing function
        logger.info(f"Processed {len(all_jobs)} jobs from API response.")
        
        # --- Filtering (using existing functions from filtering.py) ---
        filtered_jobs = all_jobs
        if request.primary_skills: # Check if primary_skills exist and are not empty
            logger.info(f"Expanding skills: {request.primary_skills}")
            # Note: expand_skills uses OpenAI sync client. Wrap in thread executor too.
            expanded_skills = await loop.run_in_executor(
                 None,
                 lambda: expand_skills(request.primary_skills) # Assumes expand_skills takes list
            )
            
            logger.info("Filtering API jobs by expanded skills...")
            # Note: filter_jobs might also be CPU-bound. Consider executor if slow.
            # Assuming filter_jobs is reasonably fast for now.
            filtered_jobs, _ = filter_jobs(all_jobs, expanded_skills) # Use existing filtering function
            logger.info(f"Filtered down to {len(filtered_jobs)} jobs matching skills.")
        else:
             logger.info("No primary skills provided, skipping skill-based filtering.")
        
        logger.info(f"Task 1 Finished: Returning {len(filtered_jobs)} filtered jobs.")
        return filtered_jobs
        
    except requests.exceptions.Timeout:
         logger.error(f"API request timed out after 20 seconds.")
         raise HTTPException(status_code=504, detail="Request to external job API timed out.")
    except requests.exceptions.RequestException as api_err:
         logger.error(f"API request failed: {api_err}")
         # Attempt to get more detail from response if available
         detail = f"External job API request failed: {api_err}"
         if hasattr(api_err, 'response') and api_err.response is not None:
              detail += f" - Status: {api_err.response.status_code}, Body: {api_err.response.text[:200]}"
         raise HTTPException(status_code=502, detail=detail) # Bad Gateway
    except Exception as e:
        logger.error(f"Error processing API jobs or filtering: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        # Raise a generic internal server error for unexpected issues
        raise HTTPException(status_code=500, detail=f"Internal error processing job results: {str(e)}")

async def fetch_profile_and_generate_query(request: JobSearchRequest) -> str:
    """Fetches user profile from Supabase and generates the optimized Pinecone query using LLM."""
    logger.info("Starting Task 2: Fetch Profile and Generate Query")
    try:
        # 1. Fetch profile using the utility function
        logger.info(f"Fetching profile for user_id: {request.user_id}")
        # Ensure fetch_user_profile is imported correctly from utils.supabase_utils
        resume_text = await fetch_user_profile(request.user_id)
        logger.info(f"Profile fetched successfully (length: {len(resume_text)}).")

        # 2. Prepare context for query generation
        # Ensure the keys here match exactly what generate_optimized_query expects
        # And that the types from JobSearchRequest match (e.g., lists for roles/skills)
        search_context = {
            "resume_text": resume_text,
            "target_roles": request.target_roles, # Assumes this is List[str] in model
            "primary_skills": request.primary_skills, # Assumes this is List[str] in model
            "location": request.preferred_location, # Assumes string
            "job_type": request.job_type, # Pass job_type (string)
            "additional_preferences": request.additional_preferences # Assumes string
        }
        logger.debug(f"Search context prepared for query generation: {search_context}") # Debug log

        # 3. Generate query using the utility function
        logger.info("Generating optimized query via LLM...")
        # Ensure generate_optimized_query is imported correctly from utils.pinecone_utils
        optimized_query = await generate_optimized_query(search_context)
        logger.info(f"Optimized query generated: '{optimized_query}...'") # Log snippet

        logger.info("Task 2 Finished: Returning optimized query.")
        return optimized_query

    except HTTPException as he:
         # If fetching profile or query gen raises HTTPException, re-raise it
         logger.error(f"HTTPException in Task 2: {he.detail}")
         raise he
    except Exception as e:
        logger.error(f"Unexpected error in fetch_profile_and_generate_query: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        # Raise a generic internal server error
        raise HTTPException(status_code=500, detail=f"Internal error generating search query: {str(e)}")

async def save_search_criteria(request: JobSearchRequest) -> Optional[int]:
     """Saves search criteria to Supabase 'job_searches' table and returns the generated ID."""
     logger.info("Attempting to save search criteria to database...")
     try:
        # Prepare data for Supabase insertion
        # Ensure lists are converted to strings if the DB column expects text
        target_roles_str = ", ".join(request.target_roles) if request.target_roles else ""
        primary_skills_str = ", ".join(request.primary_skills) if request.primary_skills else ""
        # Handle job_type (assuming it's a string in the request model now, adjust if list)
        job_type_str = request.job_type if request.job_type else "Full-time" # Default if None/empty

        search_data = {
            "user_id": request.user_id,
            "query": f"{target_roles_str} in {request.preferred_location}", # Example query string
            "target_roles": target_roles_str,
            "primary_skills": primary_skills_str,
            "location": request.preferred_location,
            "job_types": job_type_str # Ensure column name matches DB
            # Add any other relevant criteria fields to save
        }
        logger.debug(f"Search criteria data to insert: {search_data}")

        # --- Database Interaction ---
        # Note: The Supabase Python client might be synchronous.
        # Using run_in_executor to avoid blocking the event loop.
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
             None,
             lambda: supabase.table("job_searches").insert(search_data).execute()
        )
        # --- End Database Interaction ---

        # Check response and extract ID
        if result.data and len(result.data) > 0:
             db_id = result.data[0].get("id")
             if db_id:
                 logger.info(f"Saved search criteria with database ID: {db_id}")
                 return db_id
             else:
                 logger.error("Saved search criteria but 'id' key missing in response data.")
                 return None
        else:
             logger.error(f"Failed to save search criteria. Supabase response: {result}")
             return None # Indicate failure

     except Exception as db_error:
        logger.error(f"Error saving search criteria to database: {str(db_error)}")
        import traceback
        logger.error(traceback.format_exc())
        return None # Return None on failure

async def save_filtered_jobs_to_db(filtered_jobs: List[Dict], db_search_id: int):
    """Saves a list of filtered jobs to the Supabase 'filtered_jobs' table."""
    if not filtered_jobs:
        logger.info("No jobs provided to save_filtered_jobs_to_db.")
        return # Nothing to do
    if not db_search_id:
        logger.error("Cannot save filtered jobs: Missing database search ID.")
        return # Cannot proceed without the foreign key

    logger.info(f"Attempting to save {len(filtered_jobs)} filtered jobs to database for search ID: {db_search_id}...")
    
    jobs_to_insert = []
    prep_errors = 0
    for job in filtered_jobs:
        try:
            # Prepare job data dictionary matching Supabase table columns
            # Perform necessary data type conversions or checks here
            job_data = {
                "search_id": db_search_id,
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "location": job.get("location", ""),
                "description": job.get("description", ""),
                "url": job.get("apply_url", job.get("url", "")), # Prioritize apply_url
                "date_posted": job.get("date_posted", ""), # Ensure format is DB compatible
                "job_type": job.get("job_type", ""),
                # Handle skills_matched - assuming it needs to be a string
                "skills_matched": ", ".join(job.get("job_matched_skills", {}).keys()) if isinstance(job.get("job_matched_skills"), dict) else "",
                "total_skills": job.get("skills_match_count", 0)
                # Add/remove fields to exactly match your 'filtered_jobs' table schema
            }
            jobs_to_insert.append(job_data)
        except Exception as e:
            prep_errors += 1
            logger.warning(f"Error preparing job data for DB save (ID: {job.get('id', 'N/A')}, Title: {job.get('title', 'N/A')}): {str(e)}")

    if prep_errors > 0:
         logger.warning(f"{prep_errors} jobs skipped during data preparation for DB save.")

    if not jobs_to_insert:
        logger.warning("No jobs remaining to insert into database after preparation.")
        return

    try:
        logger.info(f"Inserting {len(jobs_to_insert)} prepared jobs into Supabase table 'filtered_jobs'...")
        # --- Database Interaction ---
        loop = asyncio.get_running_loop()
        insert_result = await loop.run_in_executor(
             None,
             lambda: supabase.table("filtered_jobs").insert(jobs_to_insert).execute()
        )
        # --- End Database Interaction ---

        # Log success/failure based on response
        # Supabase batch insert might not return detailed row data, check for basic success indication
        if hasattr(insert_result, 'data') and insert_result.data is not None:
             # Simplistic check, adjust based on actual Supabase client response
             logger.info(f"Successfully initiated insert for {len(jobs_to_insert)} jobs.")
        elif hasattr(insert_result, 'error') and insert_result.error:
             logger.error(f"Supabase insert failed with error: {insert_result.error}")
        else:
             logger.warning(f"Supabase insert for filtered jobs completed, but response format unexpected: {insert_result}")

    except Exception as db_error:
        logger.error(f"Error inserting filtered jobs into database: {str(db_error)}")
        import traceback
        logger.error(traceback.format_exc())
        # Do not raise here, allow the main flow to continue if possible

# --- Block 3: Refactor the /search endpoint (Orchestration Logic) ---
@router.post("/search")
async def search_jobs_orchestrator(request: JobSearchRequest):
    """
    Orchestrates the job search process using the new workflow.
    Focuses on calling helpers and utilities, sequencing steps.
    """
    logger.info(f"Received orchestrated search request for user: {request.user_id}")
    
    # --- Step A: Concurrent Preparation Tasks ---
    logger.info("Step A: Creating concurrent prep tasks...")
    api_task: Coroutine = asyncio.create_task(fetch_and_filter_api_jobs(request))
    profile_query_task: Coroutine = asyncio.create_task(fetch_profile_and_generate_query(request))

    # --- Step B: Wait for Concurrent Tasks & Save API Jobs ---
    logger.info("Step B: Waiting for prep tasks and saving API jobs...")
    try:
        task_results = await asyncio.gather(api_task, profile_query_task, return_exceptions=True)

        # Handle results/exceptions from gather
        if isinstance(task_results[0], Exception):
            raise HTTPException(status_code=500, detail=f"Failed fetch/filter API jobs: {task_results[0]}")
        filtered_api_jobs = task_results[0]

        if isinstance(task_results[1], Exception):
             raise HTTPException(status_code=500, detail=f"Failed profile/query gen: {task_results[1]}")
        optimized_query = task_results[1]

        logger.info(f"Prep tasks complete. Got {len(filtered_api_jobs)} API jobs and query: '{optimized_query[:50]}...'")

        # Save API jobs (calling placeholder)
        db_search_id = await save_search_criteria(request)
        if filtered_api_jobs and db_search_id:
            await save_filtered_jobs_to_db(filtered_api_jobs, db_search_id)

    except Exception as gather_err:
        logger.error(f"Error during Step B: {gather_err}")
        # Ensure specific exceptions are re-raised if they are HTTPExceptions
        if isinstance(gather_err, HTTPException):
             raise gather_err
        raise HTTPException(status_code=500, detail=f"Error during initial preparation: {str(gather_err)}")

    # --- Step C: Pinecone Reset & Sync from Supabase ---
    logger.info("Step C: Starting Pinecone reset and sync...")
    try:
        all_supabase_jobs = await fetch_all_supabase_filtered_jobs() # Utility call
        await delete_pinecone_namespace_vectors(PINECONE_NAMESPACE) # Utility call
        
        if all_supabase_jobs:
             sync_result = await sync_jobs_to_pinecone_utility(all_supabase_jobs, PINECONE_NAMESPACE) # Utility call
             logger.info(f"Pinecone sync completed: {sync_result.get('count', 0)} synced.")
        
             # --- INCREASE DELAY HERE ---
             wait_time = 10 # Wait for 10 seconds (Increased for testing)
             logger.info(f"Waiting {wait_time} seconds for Pinecone index to update...")
             await asyncio.sleep(wait_time)
             # --- END DELAY ---            
        
        else:
             logger.info("No Supabase jobs found to sync.")
    except Exception as sync_err:
        logger.error(f"Error during Step C: {sync_err}")
        if isinstance(sync_err, HTTPException):
             raise sync_err
        raise HTTPException(status_code=500, detail=f"Error during Pinecone sync: {str(sync_err)}")

    # --- Step D: Pinecone Search ---
    logger.info("Step D: Searching Pinecone...")
    try:
        # # --- Use Hardcoded Query for testing ---
        # test_query = """Full-time Machine Learning Engineer jobs in United States with a focus on Machine Learning, Computer Vision, Python, Deep Learning, SQL, and LLMs."""
        # logger.warning(f"!!! USING HARDCODED TEST QUERY: {test_query} !!!")
        
        # --- Wrap the SYNCHRONOUS utility call in run_in_executor ---
        loop = asyncio.get_running_loop()
        pinecone_results = await loop.run_in_executor(
            None, # Use default thread pool
            lambda: search_pinecone_jobs(optimized_query, top_k=10) # Call the sync function
        )
        # --- End wrapping ---
        
        logger.info(f"Pinecone search returned {len(pinecone_results.get('result', {}).get('hits', []))} potential matches.")
    except Exception as search_err:
        logger.error(f"Error during Step D: {search_err}")
        if isinstance(search_err, HTTPException):
             raise search_err
        raise HTTPException(status_code=500, detail=f"Error searching Pinecone: {str(search_err)}")

    # --- Step E: Fetch Details & Analyze ---
    logger.info("Step E: Fetching details and analyzing...")
    analyzed_pinecone_jobs = []
    try:
        complete_job_results = await fetch_job_details_from_supabase(pinecone_results) # Utility call
        if complete_job_results:
            user_profile_text = await fetch_user_profile(request.user_id) # Utility call (fetch again needed here)
            top_jobs_for_analysis = complete_job_results[:5]
            
            analysis_tasks = [
                 asyncio.create_task(analyze_job_fit_and_provide_tips(user_profile_text, job))
                 for job in top_jobs_for_analysis if job.get('id') and job.get('description')
            ]
            job_ids_for_analysis = [job['id'] for job in top_jobs_for_analysis if job.get('id') and job.get('description')]

            analysis_outputs = []
            if analysis_tasks:
                analysis_outputs = await asyncio.gather(*analysis_tasks, return_exceptions=True)

            # Merge results (simplified logic shown, see previous full example for detail)
            analysis_map = {
                job_id: result
                for job_id, result in zip(job_ids_for_analysis, analysis_outputs)
                if result and not isinstance(result, Exception)
            }

            for job in complete_job_results:
                 job_id = job.get('id')
                 analysis_data = analysis_map.get(job_id, {})
                 analyzed_pinecone_jobs.append({
                     **job,
                     'match_percentage': round(job.get('similarity_score', 0) * 100, 1),
                     'match_text': f"{round(job.get('similarity_score', 0) * 100)}% Match",
                     'analysis': analysis_data
                 })
            logger.info(f"Analysis complete for {len(analysis_map)} jobs.")
        else:
             logger.info("No matching jobs found in Supabase for Pinecone results.")
    except Exception as analyze_err:
         logger.error(f"Error during Step E: {analyze_err}")
         # Don't fail the whole request, just return potentially empty results
         # Consider raising if profile fetch fails, maybe?

    # --- Step F: Return Results ---
    logger.info(f"Step F: Returning {len(analyzed_pinecone_jobs)} analyzed jobs.")
    return {
        "status": "complete",
        "message": f"Found and analyzed {len(analyzed_pinecone_jobs)} jobs matching your profile.",
        "jobs": analyzed_pinecone_jobs,
        "total_jobs_found": len(analyzed_pinecone_jobs), # Or adjust meaning
        "filtered_jobs_count": len(analyzed_pinecone_jobs), # Or adjust meaning
        "search_query_used": optimized_query
    }

def process_linkedin_jobs(linkedin_jobs):
    """Process LinkedIn jobs into our standard format"""
    processed_jobs = []
    
    for job_data in linkedin_jobs:
        # Extract job description
        description = ""
        if "description_text" in job_data:
            description = job_data["description_text"]
        
        # Get employment type (full-time, part-time, etc.)
        job_type = "Full-time"
        if "employment_type" in job_data and job_data["employment_type"]:
            if isinstance(job_data["employment_type"], list) and len(job_data["employment_type"]) > 0:
                job_type = job_data["employment_type"][0]
            elif isinstance(job_data["employment_type"], str):
                job_type = job_data["employment_type"]
        
        # Handle location with better formatting
        location = ""
        if "locations_derived" in job_data and job_data["locations_derived"]:
            if isinstance(job_data["locations_derived"], list) and len(job_data["locations_derived"]) > 0:
                if isinstance(job_data["locations_derived"][0], dict):
                    location_parts = []
                    if "city" in job_data["locations_derived"][0]:
                        location_parts.append(job_data["locations_derived"][0]["city"])
                    if "admin" in job_data["locations_derived"][0]:
                        location_parts.append(job_data["locations_derived"][0]["admin"])
                    if "country" in job_data["locations_derived"][0]:
                        location_parts.append(job_data["locations_derived"][0]["country"])
                    location = ", ".join(filter(None, location_parts))
                else:
                    location = str(job_data["locations_derived"][0])
        
        # Check for remote status
        remote = False
        if "remote_derived" in job_data:
            remote = bool(job_data["remote_derived"])
        elif "location_type" in job_data and job_data["location_type"] == "TELECOMMUTE":
            remote = True
        
        # Format date in a more readable way
        date_posted = job_data.get("date_posted", "")
        try:
            if date_posted and date_posted.strip():
                from datetime import datetime
                date_obj = datetime.fromisoformat(date_posted.replace('Z', '+00:00'))
                date_posted = date_obj.strftime("%B %d, %Y")
        except Exception:
            # Keep original format if parsing fails
            pass
        
        # Get organization details
        company = job_data.get("organization", "")
        company_url = job_data.get("organization_url", "")
        company_logo = job_data.get("organization_logo", "")
        
        # Format job data in our standard structure
        job = {
            "title": job_data.get("title", ""),
            "company": company,
            "company_url": company_url,
            "company_logo": company_logo,
            "location": location,
            "job_type": job_type,
            "date_posted": date_posted,
            "description": description,
            "apply_url": job_data.get("url", ""),
            "remote": remote,
            "source": job_data.get("source", "linkedin")
        }
        processed_jobs.append(job)
    
    return processed_jobs


