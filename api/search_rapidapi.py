import os
import json
import requests
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException
from api.filtering import *
from pydantic import BaseModel
import logging
import sys
import uuid

# Configure logging first
logging.basicConfig(level=logging.INFO, stream=sys.stdout, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("job_search_api")

# Load environment variables
load_dotenv()
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

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

# Search endpoint
@router.post("/search")
async def search_jobs(request: JobSearchRequest):
    """Search for jobs and return results - synchronous for debugging"""
    logger.info(f"Received search request: {request}")
    # Print specific fields for debugging
    logger.info(f"Job type received: '{request.job_type}' (type: {type(request.job_type)})")
    logger.info(f"Target roles received: {request.target_roles} (type: {type(request.target_roles)})")
    
    try:
        # Generate a unique ID for this search
        search_id = str(uuid.uuid4())
        logger.info(f"Generated search_id: {search_id}")
        
        # Set up the API call to LinkedIn Job Search API
        url = "https://linkedin-job-search-api.p.rapidapi.com/active-jb-7d"
        
        # Format roles for title_filter
        if len(request.target_roles) > 1:
            # For multiple roles, combine with OR
            title_filter = " OR ".join([f'"{role}"' for role in request.target_roles])
        else:
            # For single role, use as is
            title_filter = f'"{request.target_roles[0]}"'
        
        # Format location for location_filter
        location_filter = f'"{request.preferred_location}"'
        
        # Map job_type to LinkedIn's format
        job_type_mapping = {
            "full-time": "FULL_TIME",
            "part-time": "PART_TIME",
            "contract": "CONTRACTOR", 
            "internship": "INTERN",
            "temporary": "TEMPORARY",
            "volunteer": "VOLUNTEER"
        }
        
        # Get the job type from the request - handle case sensitivity
        type_filter = job_type_mapping.get(request.job_type.lower() if request.job_type else "", "FULL_TIME")
        logger.info(f"Using type_filter: {type_filter} from job_type: {request.job_type}")
        
        # Prepare request parameters
        querystring = {
            "limit": "15",  # Smaller limit for testing
            "offset": "0",
            "title_filter": title_filter,
            "location_filter": location_filter,            
            "type_filter": type_filter,
            "description_type": "text"
        }
        
        logger.info(f"Prepared API query: {querystring}")
        
        # Set up headers with RapidAPI key - using format from working test
        headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": "linkedin-job-search-api.p.rapidapi.com"
        }
        
        # Make the API call directly - skipping background tasks for debugging
        logger.info("Making API request to LinkedIn...")
        response = requests.get(url, headers=headers, params=querystring)
        
        # Log the full response for debugging
        logger.info(f"Response status code: {response.status_code}")
        logger.info(f"Response headers: {response.headers}")
        try:
            logger.info(f"Response body: {response.json()}")
        except:
            logger.info(f"Raw response: {response.text}")
        
        # Check if the request was successful
        if response.status_code == 200:
            logger.info("LinkedIn API request successful")
            linkedin_jobs = response.json()
            
            # Process jobs
            all_jobs = process_linkedin_jobs(linkedin_jobs)
            logger.info(f"Processed {len(all_jobs)} jobs from LinkedIn")
            
            # Filter jobs using existing filtering.py if skills provided
            filtered_jobs = all_jobs
            try:
                if request.primary_skills and len(request.primary_skills) > 0:
                    
                    print("Expanding skills---------------")
                    # Expand skills using OpenAI
                    logger.info(f"Expanding skills: {request.primary_skills}")
                    expanded_skills = expand_skills(request.primary_skills)
                    
                    # Filter jobs by skills
                    logger.info("Filtering jobs by skills...")
                    filtered_jobs, matched_skillset = filter_jobs(all_jobs, expanded_skills)
                    logger.info(f"Filtered down to {len(filtered_jobs)} jobs matching skills")
                    print(f"FILTERED JOBS INGA IRUKU: {filtered_jobs}")
            except Exception as filter_error:
                logger.error(f"Error in skills filtering: {str(filter_error)}")
                # Continue with unfiltered jobs if filtering fails
                filtered_jobs = all_jobs
            
            # Return results directly
            return {
                "status": "complete",
                "message": f"Found {len(all_jobs)} jobs, {len(filtered_jobs)} match your skills",
                "jobs": filtered_jobs,
                "total_jobs_found": len(all_jobs),
                "filtered_jobs_count": len(filtered_jobs),
                "search_id": search_id
            }
        else:
            # Handle API error with more details
            error_msg = f"LinkedIn API request failed with status {response.status_code}"
            if response.status_code == 401:
                error_msg += " (Unauthorized - Check API key)"
            elif response.status_code == 403:
                error_msg += " (Forbidden - API key may be invalid or expired)"
            elif response.status_code == 429:
                error_msg += " (Too Many Requests - Rate limit exceeded)"
            
            logger.error(error_msg)
            logger.error(f"Response: {response.text}")
            raise HTTPException(
                status_code=500, 
                detail=error_msg
            )
    
    except Exception as e:
        logger.error(f"Error in search_jobs: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error searching for jobs: {str(e)}")

@router.get("/search/results/{search_id}")
async def get_search_results(search_id: str):
    """Get job search results by search ID"""
    results = job_results_store.get(search_id, {
        "status": "not_found",
        "message": "Search results not found",
        "jobs": [],
        "total_jobs_found": 0,
        "filtered_jobs_count": 0
    })
    return results

async def fetch_jobs_in_background(search_id: str, request: JobSearchRequest):
    """Fetch jobs using LinkedIn API in the background"""
    logger.info(f"Starting background job search for ID: {search_id}")
    logger.info(f"Search parameters: roles={request.target_roles}, location={request.preferred_location}, job_type={request.job_type}")
    
    try:
        # Update status to searching
        job_results_store[search_id] = {
            "status": "searching",
            "message": "Searching for jobs...",
            "jobs": [],
            "total_jobs_found": 0,
            "filtered_jobs_count": 0
        }
        
        # Set up the API call to LinkedIn Job Search API
        url = "https://linkedin-job-search-api.p.rapidapi.com/active-jb-7d"
        
        # Format roles for title_filter
        if len(request.target_roles) > 1:
            # For multiple roles, combine with OR
            title_filter = " OR ".join([f'"{role}"' for role in request.target_roles])
        else:
            # For single role, use as is
            title_filter = f'"{request.target_roles[0]}"'
        
        # Format location for location_filter
        location_filter = f'"{request.preferred_location}"'
        
        # Map job_type to LinkedIn's format
        job_type_mapping = {
            "full-time": "FULL_TIME",
            "part-time": "PART_TIME",
            "contract": "CONTRACTOR",
            "internship": "INTERN",
            "temporary": "TEMPORARY",
            "volunteer": "VOLUNTEER"
        }
        
        # Get the job type from the request
        type_filter = job_type_mapping.get(request.job_type.lower(), "FULL_TIME")
        
        # Prepare request parameters using the exact structure required by the API
        querystring = {
            "limit": "50",  # Only one page to limit costs
            "offset": "0",
            "title_filter": title_filter,
            "location_filter": location_filter,
            "date_posted": "week",  # Last 7 days
            "type_filter": type_filter,
            "description_type": "text"  # Include job descriptions
        }
        
        # Set up headers with RapidAPI key
        headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": "linkedin-job-search-api.p.rapidapi.com"
        }
        
        try:
            # Make the API call - just once to limit costs
            response = requests.get(url, headers=headers, params=querystring)
            print(response)
            # Check if the request was successful
            if response.status_code == 200:
                linkedin_jobs = response.json()
                
                # Process jobs
                all_jobs = process_linkedin_jobs(linkedin_jobs)
                
                # Filter jobs using the existing filtering.py functionality
                filtered_jobs = all_jobs
                if request.primary_skills and len(request.primary_skills) > 0:
                    # Import from your existing filtering module
                    from filtering import expand_skills, filter_jobs
                    
                    # Expand skills using OpenAI
                    expanded_skills = expand_skills(request.primary_skills)
                    
                    # Filter jobs by skills
                    filtered_jobs, matched_skillset = filter_jobs(all_jobs, expanded_skills)
                
                # Update final results
                job_results_store[search_id] = {
                    "status": "complete",
                    "message": f"Found {len(all_jobs)} jobs, {len(filtered_jobs)} match your skills",
                    "jobs": filtered_jobs,
                    "total_jobs_found": len(all_jobs),
                    "filtered_jobs_count": len(filtered_jobs)
                }
            else:
                # Handle API error
                job_results_store[search_id] = {
                    "status": "error",
                    "message": f"API request failed with status code: {response.status_code}",
                    "jobs": [],
                    "total_jobs_found": 0,
                    "filtered_jobs_count": 0
                }
        
        except Exception as e:
            job_results_store[search_id] = {
                "status": "error",
                "message": f"Error fetching jobs: {str(e)}",
                "jobs": [],
                "total_jobs_found": 0,
                "filtered_jobs_count": 0
            }
    
    except Exception as e:
        # Handle exceptions
        job_results_store[search_id] = {
            "status": "error",
            "message": f"Error in job search process: {str(e)}",
            "jobs": [],
            "total_jobs_found": 0,
            "filtered_jobs_count": 0
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

def filter_jobs_by_skills(jobs, skills):
    """Filter jobs based on skills match"""
    filtered_jobs = []
    lowercase_skills = [skill.lower() for skill in skills]
    
    for job in jobs:
        # Check if any of the user's skills are mentioned in the job description
        description = job.get("description", "").lower()
        title = job.get("title", "").lower()
        
        # Count how many skills match
        skill_matches = sum(1 for skill in lowercase_skills if skill in description or skill in title)
        
        # If at least one skill matches, add the job with a skill match score
        if skill_matches > 2:
            job_copy = job.copy()
            job_copy["skill_match_score"] = skill_matches
            filtered_jobs.append(job_copy)
    
    # Sort by skill match score (highest first)
    filtered_jobs.sort(key=lambda x: x.get("skill_match_score", 0), reverse=True)
    
    return filtered_jobs

# Add a simple test endpoint
@router.get("/test")
async def test_endpoint():
    """Simple test endpoint to verify API is working"""
    logger.info("Test endpoint hit successfully")
    return {"status": "success", "message": "API is working correctly"}
