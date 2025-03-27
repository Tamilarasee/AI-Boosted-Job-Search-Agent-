from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from openai import OpenAI
from dotenv import load_dotenv
import json
import traceback
from api.filtering import expand_skills, filter_jobs

import openai
print(f"OpenAI version: {openai.__version__}")
# Load environment variables
load_dotenv()

router = APIRouter()

# Initialize OpenAI client
client = OpenAI()

# Define the data model for job search
class JobSearchRequest(BaseModel):
    target_roles: List[str]
    primary_skills: List[str]
    preferred_location: str
    job_type: Optional[str] = None
    additional_preferences: Optional[str] = None

# Define our JSON schema for job listings
job_schema = {
    "type": "object",
    "properties": {
        "jobs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "location": {"type": "string"},
                    "date_posted": {"type": "string"},
                    "description": {"type": "string"},
                    "company": {"type": "string"},
                    "apply_url": {"type": "string"}
                },
                "required": ["title", "location", "date_posted", "description", "apply_url"]
            }
        }
    }
}

@router.post("/search")
async def search_jobs(request: JobSearchRequest):
    try:
        # Construct the search query using target roles and location
        search_query = f"{', '.join(request.target_roles)} jobs in {request.preferred_location}"
        
        # Create the system message for the AI
        system_message = f"""You are a job search assistant. Find real job postings and return them in a specific JSON format.
        
        INSTRUCTIONS:
        1. ONLY return actual job listings with application links - no articles, blogs, or other content
        2. Prioritize the latest job postings that meets the criteria
        3. We need 500 jobs definitely, If there are more than 500 job postings matching the criteria, return only the latest 500
        4. If you can't find enough matches for ALL criteria, relax the criteria but within the same country of the location
        5. We do not want to miss any relevant job postings posted in the 7 days.
        6. Directly give the json output, do not include any other text or comments or unneccesary formatting, directly start with "jobs": [.

        OUTPUT FORMAT{job_schema}       
        Return results as a JSON array of job objects."""
        
        # Create the user message with search criteria
        user_message = f"Find job postings for: {search_query}. Focus on recent postings within the last month."
        
        # Make the API call to OpenAI
        response = client.responses.create(
            model="gpt-4o",
            tools=[{ "type": "web_search_preview" }],
            input=user_message,
            instructions=system_message
            #format={"type": "json_schema", "schema": job_schema}
        )
        
        # Find the "message" type output regardless of its position
        message_output = None
        for output_item in response.output:
            if hasattr(output_item, 'type') and output_item.type == 'message':
                message_output = output_item
                break
                
        if not message_output or not hasattr(message_output, 'content') or not message_output.content:
            raise ValueError("No message content found in response")
            
        # Get text content from the message
        text_content = message_output.content[0].text
        
        # Clean up the text content to extract JSON
        # Remove markdown code blocks
        import re
        json_text = text_content
        
        # Remove markdown code formatting
        json_text = re.sub(r'```json\s*|\s*```', '', json_text)
        
        # Trim whitespace
        json_text = json_text.strip()
        
        try:
            # Try parsing the cleaned text as JSON
            job_data = json.loads(json_text)
            
            # Handle both a direct array or an object with a jobs property
            if isinstance(job_data, list):
                jobs = job_data
            else:
                jobs = job_data.get("jobs", [])
                
        except json.JSONDecodeError:
            # If that fails, try more aggressive extraction
            try:
                # Find anything that looks like a JSON object or array
                json_pattern = r'(\{[\s\S]*\}|\[[\s\S]*\])'
                match = re.search(json_pattern, json_text)
                
                if match:
                    json_candidate = match.group(0)
                    job_data = json.loads(json_candidate)
                    
                    if isinstance(job_data, list):
                        jobs = job_data
                    else:
                        jobs = job_data.get("jobs", [])
                else:
                    jobs = []
            except:
                jobs = []
        
        print("\n\nHERE ARE THE JOBS", jobs , "\n\n")
        print("JOB LENGTH", len(jobs))

        expanded_skills = expand_skills(request.primary_skills)
        filtered_jobs, skillset = filter_jobs(jobs, expanded_skills,min_skills_match=3)

        return {
            "total_jobs_found": len(jobs),
            "filtered_jobs_count": len(filtered_jobs),
            "expanded_skills": skillset,
            "jobs": filtered_jobs
        }
        
                
    except Exception as e:
        
        print(f"Error searching for jobs: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error searching for jobs: {str(e)}")
    
