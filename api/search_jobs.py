from fastapi import APIRouter, HTTPException, BackgroundTasks
import os
import re
import uuid
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel
import httpx
import asyncio
from utils.supabase.db import supabase
from dotenv import load_dotenv
import json
import time

# Load environment variables
load_dotenv()

router = APIRouter()

class JobSearchQuery(BaseModel):
    target_roles: str
    primary_skills: str
    location_preference: Optional[str] = None
    job_type: Optional[List[str]] = None
    additional_preferences: Optional[str] = None
    user_id: Optional[str] = None
    date_posted: Optional[str] = "7 Days" 

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
    """Background task to fetch jobs using OpenAI"""
    try:
        print(f"Starting OpenAI job search for search_id: {search_id}")
        search_status_cache[search_id] = "in_progress"
        
        # Break down the primary skills into a list
        primary_skills = [skill.strip() for skill in query.primary_skills.split(',')]
        
        # Search for jobs using OpenAI
        job_listings = await execute_openai_search(query)
        print(f"Found {len(job_listings)} jobs using OpenAI search")
        
        # Process and filter the job listings
        all_filtered_jobs = []
        for job in job_listings:
            # Get job description
            description = job.get("description", "").lower()
            
            # Check if job has at least 2 of the required skills
            matched_skills = skills_match_count(description, primary_skills)
            
            if matched_skills >= 2 or len(primary_skills) <= 1:
                # Format job details
                job_details = {
                    "title": job.get("title", "Unknown Position"),
                    "company": job.get("company", "Unknown Company"),
                    "location": job.get("location", "Unknown Location"),
                    "description": job.get("description", ""),
                    "url": job.get("url", ""),
                    "date_posted": job.get("date_posted", "Recent"),
                    "salary": job.get("salary", "Not specified"),
                    "job_type": job.get("job_type", ""),
                    "experience_level": job.get("experience_level", "Not specified"),
                    "source": "AI Job Search",
                    "skills_matched": matched_skills,
                    "total_skills": len(primary_skills)
                }
                
                # Save job to database
                saved = await save_job_to_db(job_details, search_id)
                if saved:
                    all_filtered_jobs.append(job_details)
        
        # Update the cache
        job_results_cache[search_id] = all_filtered_jobs
        
        # Mark search as complete
        search_status_cache[search_id] = "complete"
        
        # Update the search record to mark it as complete
        if query.user_id:
            try:
                supabase.table("job_searches").update({
                    "is_complete": True,
                    "total_jobs_found": len(all_filtered_jobs)
                }).eq("id", search_id).execute()
            except Exception as e:
                print(f"Error updating search status: {str(e)}")
        
        print(f"Job search complete for {search_id}. Total filtered jobs: {len(all_filtered_jobs)}")
        
    except Exception as e:
        print(f"Error in background job fetching with OpenAI: {str(e)}")
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
    Search for jobs using OpenAI's web browsing capability
    Returns initial results and continues searching in background
    """
    # Generate a unique search ID
    search_id = str(uuid.uuid4())
    
    # Construct search query for display
    location_str = f" in {query.location_preference}" if query.location_preference else ""
    job_type_str = ""
    if query.job_type and len(query.job_type) > 0:
        job_type_str = f" ({', '.join(query.job_type)})"
    
    experience_str = f" {query.experience_level}" if query.experience_level and query.experience_level != "Any Level" else ""
    date_str = f" posted within {query.date_posted}" if query.date_posted else " posted recently"
    
    search_query = f"{experience_str} {query.target_roles} jobs{job_type_str}{location_str}{date_str}"
    
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
                "experience_level": query.experience_level or "Any Level",
                "date_posted": query.date_posted or "7 Days",
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
        
        # Get initial results (empty at first since we'll search in background)
        formatted_jobs = []
        
        # Store initial results in cache
        job_results_cache[search_id] = formatted_jobs
        search_status_cache[search_id] = "starting"
        
        # Start background task to fetch jobs with OpenAI
        background_tasks.add_task(background_job_fetching, search_id, query)
        
        return {
            "jobs": formatted_jobs,
            "search_query": search_query,
            "total_jobs": len(formatted_jobs),
            "search_id": search_id,
            "is_complete": False
        }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching for jobs: {str(e)}")

@router.get("/job-search/{search_id}", response_model=JobSearchResponse)
async def get_job_results(search_id: str):
    """
    Get job search results for a specific search ID
    Allows polling for more results after initial search
    """
    # Debug print
    print(f"Received request for search_id: {search_id}")
    print(f"Available search IDs in cache: {list(job_results_cache.keys())}")
    
    if search_id not in job_results_cache:
        # Try to fetch from database if not in memory
        try:
            jobs_result = supabase.table("jobs").select("*").eq("search_id", search_id).execute()
            if jobs_result.data:
                jobs = jobs_result.data
                search_result = supabase.table("job_searches").select("*").eq("id", search_id).execute()
                is_complete = search_result.data[0]["is_complete"] if search_result.data else False
                
                # Format the results
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
                        "source": job.get("source", "AI Job Search"),
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
            
            # If we got here, the search isn't in the database either
            print(f"Search ID {search_id} not found in database")
            
            # Check if this is a search that was recently started but hasn't saved results yet
            if search_id in search_status_cache and search_status_cache[search_id] == "starting":
                # Return an empty result but indicate search is still running
                return {
                    "jobs": [],
                    "search_query": "Jobs matching your skills",
                    "total_jobs": 0,
                    "search_id": search_id,
                    "is_complete": False
                }
            
            # Otherwise, truly not found
            raise HTTPException(status_code=404, detail="Search results not found")
        except Exception as e:
            print(f"Error fetching from database: {str(e)}")
            raise HTTPException(status_code=404, detail=f"Error fetching search results: {str(e)}")
    
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

async def execute_openai_search(query: JobSearchQuery) -> List[Dict[str, Any]]:
    """Execute an OpenAI search with the user's filters"""
    try:
        # Process date filter
        date_filter = "7 days"  # Default
        if query.date_posted:
            if query.date_posted == "Today":
                date_filter = "today"
            else:
                # Extract number from strings like "3 Days"
                days_match = re.search(r'(\d+)', query.date_posted)
                if days_match:
                    date_filter = f"the last {days_match.group(1)} days"
        
        # Process experience level filter
        experience_filter = ""
        if query.experience_level and query.experience_level != "Any Level":
            experience_filter = f"for {query.experience_level} positions"
        
        # Process job type
        job_type_filter = ""
        if query.job_type and len(query.job_type) > 0:
            job_type_filter = f"that are {', '.join(query.job_type)}"
        
        # Make the search query more specific and direct
        search_instructions = (
            f"Find job listings for {query.target_roles} positions "
            f"{experience_filter} {job_type_filter} posted within {date_filter}"
        )
        
        if query.location_preference:
            search_instructions += f" in {query.location_preference}"
        
        # Create more explicit system instructions
        system_instructions = f"""
        You are a job search assistant. Your ONLY task is to find REAL job postings matching these criteria:
        
        SEARCH CRITERIA:
        - Role/Title: {query.target_roles}
        - Skills needed: {query.primary_skills}
        - Location: {query.location_preference or "Any"}
        - Posted within: {date_filter}
        - Experience level: {query.experience_level or "Any level"}
        - Job type: {', '.join(query.job_type) if query.job_type else "Any"}
        
        INSTRUCTIONS:
        1. Search ONLY job posting websites like LinkedIn Jobs, Indeed, Glassdoor, ZipRecruiter, and company career pages
        2. Find AT LEAST 10 job listings that match the criteria
        3. For each job, extract: Title, Company, Location, URL, Description, Date Posted, Salary, Job Type
        4. ONLY return actual job listings with application links - no articles, blogs, or other content
        5. If you can't find enough matches for ALL criteria, relax the criteria but prioritize role and skills matches
        
        FORMAT: Return results as a JSON array with these fields for each job:
        - title: The job title
        - company: The company name
        - location: Where the job is located
        - url: Direct link to apply
        - description: Brief job description
        - date_posted: When the job was posted
        - salary: Salary information if available
        - job_type: Full-time, part-time, etc.
        
        Your entire response should be ONLY the JSON array of job listings.
        """
        
        # Create an assistant with web browsing capability
        assistant = client.beta.assistants.create(
            name="Job Search Assistant",
            instructions=system_instructions,
            model="gpt-4o",
            tools=[{"type": "web_browser"}]
        )
        
        # Create a thread
        thread = client.beta.threads.create()
        
        # Add a message to the thread
        message = client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=f"{search_instructions}\n\nFind at least 10 job listings matching these criteria and return them as JSON."
        )
        
        # Run the assistant with a longer timeout
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant.id
        )
        
        # Wait for the run to complete (with a longer timeout)
        max_wait_time = 120  # 2 minutes
        start_time = time.time()
        
        print(f"Waiting for OpenAI search to complete...")
        
        while run.status in ["queued", "in_progress"]:
            if time.time() - start_time > max_wait_time:
                print(f"OpenAI search timed out after {max_wait_time} seconds")
                break
                
            await asyncio.sleep(5)  # Check every 5 seconds
            run = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
            print(f"OpenAI search status: {run.status}, elapsed time: {time.time() - start_time:.1f}s")
        
        # Check if the run completed successfully
        if run.status != "completed":
            print(f"OpenAI search failed with status: {run.status}")
            
            # Fall back to a simpler search if the main one fails
            return await fallback_search(query)
        
        # Get the messages from the thread
        messages = client.beta.threads.messages.list(
            thread_id=thread.id
        )
        
        # Extract job listings from the assistant's response
        job_listings = []
        for message in messages.data:
            if message.role == "assistant":
                for content in message.content:
                    if content.type == "text":
                        text = content.text.value
                        print(f"Raw OpenAI response: {text[:200]}...")  # Print first 200 chars
                        
                        try:
                            # Look for JSON array in the text
                            json_match = re.search(r'\[\s*\{.*\}\s*\]', text, re.DOTALL)
                            if json_match:
                                json_str = json_match.group(0)
                                jobs_data = json.loads(json_str)
                                for job in jobs_data:
                                    if validate_job_posting(job):
                                        job_listings.append(job)
                            else:
                                # Try parsing the entire text as JSON
                                try:
                                    jobs_data = json.loads(text)
                                    if isinstance(jobs_data, list):
                                        for job in jobs_data:
                                            if validate_job_posting(job):
                                                job_listings.append(job)
                                except:
                                    print("Failed to parse entire text as JSON")
                        except Exception as e:
                            print(f"Error parsing OpenAI response: {str(e)}")
        
        print(f"Found {len(job_listings)} valid job listings from OpenAI search")
        
        # If no jobs found, try the fallback search
        if not job_listings:
            print("No jobs found from primary search, trying fallback...")
            return await fallback_search(query)
            
        # Clean up - delete the assistant
        client.beta.assistants.delete(assistant.id)
        
        return job_listings
    
    except Exception as e:
        print(f"Error in execute_openai_search: {str(e)}")
        # Try fallback search if main search fails
        return await fallback_search(query)

async def fallback_search(query: JobSearchQuery) -> List[Dict[str, Any]]:
    """Fallback search method that uses a more relaxed approach"""
    try:
        print("Executing fallback search...")
        
        # Create a simpler, more direct prompt
        system_message = f"""
        Find job listings for {query.target_roles}. Focus ONLY on actual job postings.
        I'm looking for positions that require these skills: {query.primary_skills}.
        Return results in JSON format with these fields:
        title, company, location, url, description, date_posted, salary, job_type
        """
        
        # Use the ChatCompletion API directly for a simpler approach
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a job search assistant that finds real job postings."},
                {"role": "user", "content": system_message}
            ],
            tools=[{"type": "web_browsing"}],
            tool_choice={"type": "web_browsing"},
            temperature=0.5,
            max_tokens=4000
        )
        
        # Extract the text
        text = response.choices[0].message.content
        print(f"Fallback search response: {text[:200]}...")  # Print first 200 chars
        
        # Parse the JSON from the response
        job_listings = []
        try:
            # Look for JSON in the text
            json_match = re.search(r'\[\s*\{.*\}\s*\]', text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                jobs_data = json.loads(json_str)
                for job in jobs_data:
                    job_listings.append(job)
            else:
                # Try parsing the entire text
                try:
                    jobs_data = json.loads(text)
                    if isinstance(jobs_data, list):
                        job_listings.extend(jobs_data)
                except:
                    print("Failed to parse fallback response as JSON")
        except Exception as e:
            print(f"Error parsing fallback response: {str(e)}")
        
        print(f"Found {len(job_listings)} job listings from fallback search")
        return job_listings
        
    except Exception as e:
        print(f"Fallback search failed: {str(e)}")
        # Return empty list if even the fallback fails
        return []

def validate_job_posting(job):
    """Verify if the result is a real job posting"""
    required_fields = ["title", "company", "url"]
    if not all(field in job and job[field] for field in required_fields):
        return False
        
    # Check URL pattern - most job URLs follow specific patterns
    job_url_patterns = [
        "/job/", "/jobs/", "/career", "/apply", "careers.",
        "jobs.", "glassdoor", "linkedin.com/jobs", "indeed"
    ]
    
    if not any(pattern in job["url"].lower() for pattern in job_url_patterns):
        # If URL doesn't look like a job posting URL, check if it's a company site
        company_patterns = [".com", ".org", ".io", ".net", ".co"]
        if not any(pattern in job["url"].lower() for pattern in company_patterns):
            return False
    
    return True

async def search_jobs_with_openai_chunked(query: JobSearchQuery) -> List[Dict[str, Any]]:
    """Use multiple OpenAI searches to get more comprehensive results"""
    all_jobs = []
    seen_urls = set()
    
    # Create different search chunks
    search_variations = [
        f"{query.target_roles} jobs in {query.location_preference or 'remote'} posted this week",
        f"entry level {query.target_roles} jobs in {query.location_preference or 'USA'} recent postings",
        f"experienced {query.target_roles} jobs {query.location_preference or ''} last 7 days",
        f"{query.target_roles} {query.primary_skills} jobs {query.location_preference or ''}"
    ]
    
    # Add job type variations
    if query.job_type:
        for job_type in query.job_type:
            search_variations.append(
                f"{job_type} {query.target_roles} jobs in {query.location_preference or 'USA'}"
            )
    
    # Process each search variation
    for search_query in search_variations:
        # Execute the search with specific instructions to find different results
        results = await execute_openai_search(
            search_query=search_query,
            skills=query.primary_skills,
            # Ask for results that haven't been seen in previous searches
            additional_instructions=f"Find different job postings than these URLs: {', '.join(list(seen_urls)[:5])}" 
            if seen_urls else ""
        )
        
        # Deduplicate by URL
        for job in results:
            if job["url"] not in seen_urls and validate_job_posting(job):
                seen_urls.add(job["url"])
                all_jobs.append(job)
                
        print(f"Found {len(results)} jobs for query '{search_query}', total unique jobs: {len(all_jobs)}")
        
        # If we have enough jobs, we can stop
        if len(all_jobs) >= 100:
            break
            
        # Sleep between requests to avoid rate limits
        await asyncio.sleep(1)
    
    return all_jobs[:100]  # Limit to 100 jobs maximum