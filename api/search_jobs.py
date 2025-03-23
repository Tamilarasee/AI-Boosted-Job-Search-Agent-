from fastapi import APIRouter, HTTPException, BackgroundTasks
import os
import re
import uuid
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel
import httpx
import asyncio
from supabase import create_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get SerpAPI key from environment
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
if not SERPAPI_KEY:
    raise ValueError("SERPAPI_KEY environment variable not set")

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase credentials not set")

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

router = APIRouter()

class JobSearchQuery(BaseModel):
    target_roles: str
    primary_skills: str
    location_preference: Optional[str] = None
    job_type: Optional[List[str]] = None
    additional_preferences: Optional[str] = None
    user_id: Optional[str] = None  # User ID for associating jobs with a user

class JobSearchResponse(BaseModel):
    jobs: List[Dict[str, Any]]
    search_query: str
    total_jobs: int
    search_id: str
    is_complete: bool = False
    has_more_pages: bool = False

# Store job results in memory for background processing
job_results_cache = {}
search_status_cache = {}

# Add these as constants at the top of the file
MAX_PAGES_TO_FETCH = 10  # Maximum pages to fetch (about 100 jobs)
MAX_JOBS_TO_STORE = 200  # Maximum jobs to store after filtering

async def fetch_jobs_with_serpapi(params: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Helper function to fetch jobs from SerpAPI with given parameters
    Returns a tuple of (jobs_list, next_page_token)
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://serpapi.com/search",
            params=params,
            timeout=30.0
        )
        
        if response.status_code != 200:
            print(f"Error fetching jobs: {response.text}")
            return [], None
        
        data = response.json()
        jobs = data.get("jobs_results", [])
        
        # Log the response structure for debugging
        print(f"Found {len(jobs)} jobs in this page")
        if "serpapi_pagination" in data:
            print(f"Pagination info: {data['serpapi_pagination']}")
        
        # Get pagination information
        pagination = data.get("serpapi_pagination", {})
        next_page_token = pagination.get("next_page_token")
        
        return jobs, next_page_token

def skills_match_count(job_description: str, skills: List[str]) -> int:
    """Count how many skills from the list appear in the job description"""
    if not job_description or not skills:
        return 0
        
    job_description = job_description.lower()
    match_count = 0
    
    for skill in skills:
        if not skill.strip():
            continue
        # Look for the skill as a whole word
        pattern = r'\b' + re.escape(skill.lower()) + r'\b'
        if re.search(pattern, job_description):
            match_count += 1
            
    return match_count

async def save_job_to_db(job_data: Dict[str, Any], search_id: str) -> bool:
    """Save a job to the database"""
    try:
        # Create a unique external ID to avoid duplicates
        external_id = f"{job_data['title']}-{job_data['company']}-{job_data['url']}"
        
        # Check if job already exists
        existing_job = supabase.table("jobs").select("id").eq("external_id", external_id).execute()
        
        # If job already exists, don't insert again
        if existing_job.data and len(existing_job.data) > 0:
            return False
        
        # Prepare job data
        db_job = {
            "id": str(uuid.uuid4()),
            "search_id": search_id,
            "title": job_data.get("title", "Unknown Position"),
            "company": job_data.get("company", "Unknown Company"),
            "location": job_data.get("location", "Unknown Location"),
            "description": job_data.get("description", ""),
            "url": job_data.get("url", ""),
            "date_posted": job_data.get("date_posted", ""),
            "salary": job_data.get("salary", ""),
            "job_type": job_data.get("job_type", ""),
            "source": job_data.get("source", ""),
            "skills_matched": job_data.get("skills_matched", 0),
            "total_skills": job_data.get("total_skills", 0),
            "external_id": external_id
        }
        
        # Insert job
        result = supabase.table("jobs").insert(db_job).execute()
        
        return True
    except Exception as e:
        print(f"Error saving job to database: {str(e)}")
        return False

async def background_job_fetching(search_id: str, query: JobSearchQuery):
    """Background task to fetch more jobs after initial results are returned"""
    try:
        print(f"Starting background job fetching for search_id: {search_id}")
        search_status_cache[search_id] = "in_progress"
        page_number = 1  # Track which page we're processing
        
        # Break down the primary skills into a list
        primary_skills = [skill.strip() for skill in query.primary_skills.split(',')]
        
        # Base search parameters
        base_params = {
            "api_key": SERPAPI_KEY,
            "engine": "google_jobs",
            "q": f"{query.target_roles} jobs",
            "hl": "en",
            "chips": "date_posted:week",  # Last 7 days
            "sort_by": "date"  # Sort by date (most recent first)
        }
        
        # Add location if specified - make sure it's included
        if query.location_preference:
            base_params["location"] = query.location_preference
            print(f"Including location in background search: {query.location_preference}")
        
        # Store all qualified jobs
        all_filtered_jobs = []
        seen_jobs = set()
        
        # Get the next page token from initial search
        next_page_token = job_results_cache.get(f"{search_id}_next_token")
        
        # Fetch subsequent pages (page 1 was already fetched in the initial request)
        page_number = 2
        
        # Continue until we hit our page limit or job limit
        while (page_number <= MAX_PAGES_TO_FETCH and 
               next_page_token and 
               len(all_filtered_jobs) < MAX_JOBS_TO_STORE):
            try:
                # Update params with the next page token
                params = base_params.copy()
                params["next_page_token"] = next_page_token
                
                # Log page processing
                print(f"Processing page #{page_number} with next_page_token")
                
                # Fetch jobs for this page
                jobs_batch, next_page_token = await fetch_jobs_with_serpapi(params)
                print(f"Page #{page_number}: Found {len(jobs_batch)} jobs from API")
                
                # If no jobs, we've reached the end
                if not jobs_batch:
                    print(f"No more jobs found on page #{page_number}")
                    break
                
                # Track filtered jobs for this page
                page_filtered_jobs = 0
                
                # Process each job
                for job in jobs_batch:
                    # Stop if we've hit our job limit
                    if len(all_filtered_jobs) >= MAX_JOBS_TO_STORE:
                        print(f"Reached maximum job limit of {MAX_JOBS_TO_STORE}")
                        break
                
                    # Create a unique identifier
                    job_url = job.get("apply_link", {}).get("link", "") or job.get("apply_options", [{}])[0].get("link", "")
                    job_identifier = f"{job.get('title', '')}-{job.get('company_name', '')}-{job_url}"
                    
                    # Skip if we've seen this job before
                    if job_identifier in seen_jobs:
                        continue
                    
                    seen_jobs.add(job_identifier)
                    
                    # Get job description
                    description = job.get("description", "").lower()
                    
                    # Check if job has at least 2 of the required skills
                    matched_skills = skills_match_count(description, primary_skills)
                    
                    if matched_skills >= 2 or len(primary_skills) <= 1:
                        # Format job details
                        job_details = {
                            "title": job.get("title", "Unknown Position"),
                            "company": job.get("company_name", "Unknown Company"),
                            "location": job.get("location", "Unknown Location"),
                            "description": job.get("description", ""),
                            "url": job_url,
                            "date_posted": job.get("detected_extensions", {}).get("posted_at", ""),
                            "salary": job.get("detected_extensions", {}).get("salary", "Not specified"),
                            "job_type": job.get("detected_extensions", {}).get("job_type", ""),
                            "source": "Google Jobs",
                            "skills_matched": matched_skills,
                            "total_skills": len(primary_skills),
                            "page": page_number  # Track which page this job came from
                        }
                        
                        # Save job to database
                        saved = await save_job_to_db(job_details, search_id)
                        if saved:
                            page_filtered_jobs += 1
                        
                        all_filtered_jobs.append(job_details)
                
                # Log page results
                print(f"Page #{page_number}: Filtered down to {page_filtered_jobs} matching jobs")
                print(f"Total jobs so far: {len(all_filtered_jobs)}")
                
                # Update the cache after each successful page
                job_results_cache[search_id] = all_filtered_jobs
                
                # Store the next page token for resuming if needed
                if next_page_token:
                    job_results_cache[f"{search_id}_next_token"] = next_page_token
                
                # If no next page token, we're done
                if not next_page_token:
                    print(f"No next page token after page #{page_number}")
                    break
                
                # Check if we've reached our job limit
                if len(all_filtered_jobs) >= MAX_JOBS_TO_STORE:
                    print(f"Reached maximum job limit of {MAX_JOBS_TO_STORE}")
                    break
                
                # Increment page number
                page_number += 1
                
                # Add a small delay between pages to avoid rate limiting
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"Error processing page #{page_number}: {str(e)}")
                break
        
        # Log the reason we stopped
        if page_number > MAX_PAGES_TO_FETCH:
            print(f"Stopped after reaching maximum page limit ({MAX_PAGES_TO_FETCH})")
        elif len(all_filtered_jobs) >= MAX_JOBS_TO_STORE:
            print(f"Stopped after reaching maximum job limit ({MAX_JOBS_TO_STORE})")
        elif not next_page_token:
            print("Stopped because there are no more pages available")
        else:
            print("Stopped due to an error or other condition")
        
        # Mark search as complete
        search_status_cache[search_id] = "complete"
        
        # Update the search record to mark it as complete
        if query.user_id:
            try:
                supabase.table("job_searches").update({
                    "is_complete": True,
                    "total_jobs_found": len(all_filtered_jobs),
                    "total_pages": page_number - 1,
                    "stop_reason": get_stop_reason(page_number, len(all_filtered_jobs), next_page_token)
                }).eq("id", search_id).execute()
            except Exception as e:
                print(f"Error updating search status: {str(e)}")
        
        print(f"Job search complete for {search_id}. Processed {page_number-1} pages. Total filtered jobs: {len(all_filtered_jobs)}")
        
    except Exception as e:
        print(f"Error in background job fetching: {str(e)}")
        search_status_cache[search_id] = "error"

def get_stop_reason(page_number, job_count, next_page_token):
    """Get the reason why the search stopped"""
    if page_number > MAX_PAGES_TO_FETCH:
        return "Reached page limit"
    elif job_count >= MAX_JOBS_TO_STORE:
        return "Reached job limit"
    elif not next_page_token:
        return "No more pages available"
    else:
        return "Error or unknown"

@router.post("/job-search", response_model=JobSearchResponse)
async def search_jobs(query: JobSearchQuery, background_tasks: BackgroundTasks):
    """
    Search for jobs using Google Jobs via SerpAPI
    Returns initial results quickly and continues fetching more in background
    """
    # Generate a unique search ID
    search_id = str(uuid.uuid4())
    
    # Construct search query
    search_query = f"{query.target_roles} jobs"
    
    # Split primary skills into a list
    primary_skills = [skill.strip() for skill in query.primary_skills.split(',')]
    
    try:
        # Create a record for this search
        if query.user_id:
            job_search_record = {
                "id": search_id,
                "user_id": query.user_id,
                "query": search_query,
                "target_roles": query.target_roles,
                "primary_skills": query.primary_skills,
                "location": query.location_preference or "",
                "job_types": query.job_type or [],
                "is_complete": False
            }
            
            try:
                supabase.table("job_searches").insert(job_search_record).execute()
            except Exception as e:
                print(f"Error creating search record: {str(e)}")
        
        # Get initial results quickly - focusing on last 7 days and sorting by date
        initial_params = {
            "api_key": SERPAPI_KEY,
            "engine": "google_jobs",
            "q": search_query,
            "hl": "en",
            "chips": "date_posted:week",  # Last 7 days
            "sort_by": "date"  # Sort by date (most recent first)
        }
        
        # Add location if specified - ensure it's included in the API request
        if query.location_preference:
            initial_params["location"] = query.location_preference
            print(f"Including location in search: {query.location_preference}")
        
        # Get initial results and next page token
        initial_results, next_page_token = await fetch_jobs_with_serpapi(initial_params)
        
        # Store next page token for background processing
        if next_page_token:
            job_results_cache[f"{search_id}_next_token"] = next_page_token
        
        # Filter and format initial results
        formatted_jobs = []
        for job in initial_results:
            # Get job description
            description = job.get("description", "").lower()
            
            # Check if job has at least 2 of the required skills
            matched_skills = skills_match_count(description, primary_skills)
            
            if matched_skills >= 2 or len(primary_skills) <= 1:
                job_url = job.get("apply_link", {}).get("link", "") or job.get("apply_options", [{}])[0].get("link", "")
                job_details = {
                    "title": job.get("title", "Unknown Position"),
                    "company": job.get("company_name", "Unknown Company"),
                    "location": job.get("location", "Unknown Location"),
                    "description": job.get("description", ""),
                    "url": job_url,
                    "date_posted": job.get("detected_extensions", {}).get("posted_at", ""),
                    "salary": job.get("detected_extensions", {}).get("salary", "Not specified"),
                    "job_type": job.get("detected_extensions", {}).get("job_type", ""),
                    "source": "Google Jobs",
                    "skills_matched": matched_skills,
                    "total_skills": len(primary_skills),
                    "page": 1  # First page
                }
                
                # Save job to database
                await save_job_to_db(job_details, search_id)
                
                formatted_jobs.append(job_details)
        
        # Store initial results in cache
        job_results_cache[search_id] = formatted_jobs
        search_status_cache[search_id] = "starting"
        
        # Start background task to fetch more results
        background_tasks.add_task(background_job_fetching, search_id, query)
        
        return {
            "jobs": formatted_jobs,
            "search_query": search_query,
            "total_jobs": len(formatted_jobs),
            "search_id": search_id,
            "is_complete": False,
            "has_more_pages": next_page_token is not None
        }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching for jobs: {str(e)}")

@router.get("/job-search/{search_id}", response_model=JobSearchResponse)
async def get_job_results(search_id: str):
    """
    Get job search results for a specific search ID
    Allows polling for more results after initial search
    """
    if search_id not in job_results_cache:
        # Try to fetch from database if not in memory
        try:
            jobs_result = supabase.table("jobs").select("*").eq("search_id", search_id).execute()
            if jobs_result.data:
                jobs = jobs_result.data
                search_result = supabase.table("job_searches").select("*").eq("id", search_id).execute()
                is_complete = search_result.data[0]["is_complete"] if search_result.data else False
                
                # Format the results to match our schema
                formatted_jobs = []
                for job in jobs:
                    formatted_jobs.append({
                        "title": job.get("title", "Unknown Position"),
                        "company": job.get("company", "Unknown Company"),
                        "location": job.get("location", "Unknown Location"),
                        "description": job.get("description", ""),
                        "url": job.get("url", ""),
                        "date_posted": job.get("date_posted", ""),
                        "salary": job.get("salary", "Not specified"),
                        "job_type": job.get("job_type", ""),
                        "source": job.get("source", "Google Jobs"),
                        "skills_matched": job.get("skills_matched", 0),
                        "total_skills": job.get("total_skills", 0)
                    })
                
                return {
                    "jobs": formatted_jobs,
                    "search_query": "Jobs matching your skills",
                    "total_jobs": len(formatted_jobs),
                    "search_id": search_id,
                    "is_complete": is_complete
                }
            
            raise HTTPException(status_code=404, detail="Search results not found")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching search results: {str(e)}")
    
    jobs = job_results_cache[search_id]
    status = search_status_cache.get(search_id, "unknown")
    is_complete = status == "complete"
    
    return {
        "jobs": jobs,
        "search_query": "Jobs matching your skills",
        "total_jobs": len(jobs),
        "search_id": search_id,
        "is_complete": is_complete
    }

@router.get("/jobs/user/{user_id}", response_model=List[Dict[str, Any]])
async def get_user_job_searches(user_id: str):
    """
    Get all job searches for a specific user
    """
    try:
        # Get all searches for this user
        searches = supabase.table("job_searches").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        
        if not searches.data:
            return []
        
        return searches.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching user job searches: {str(e)}")