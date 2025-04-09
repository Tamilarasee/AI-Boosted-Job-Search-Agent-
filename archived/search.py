# from fastapi import APIRouter, HTTPException
# from pydantic import BaseModel
# from typing import List, Optional
# from openai import OpenAI
# from dotenv import load_dotenv
# import json
# import traceback
# from api.filtering import expand_skills, filter_jobs
# import time
# from datetime import datetime

# import openai
# #print(f"OpenAI version: {openai.__version__}")
# # Load environment variables
# load_dotenv()

# router = APIRouter()

# # Initialize OpenAI client
# client = OpenAI()

# # Define the data model for job search
# class JobSearchRequest(BaseModel):
#     target_roles: List[str]
#     primary_skills: List[str]
#     preferred_location: str
#     job_type: Optional[str] = None
#     additional_preferences: Optional[str] = None

# # Define our JSON schema for job listings
# job_schema = {
#     "type": "object",
#     "properties": {
#         "jobs": {
#             "type": "array",
#             "items": {
#                 "type": "object",
#                 "properties": {
#                     "title": {"type": "string"},
#                     "location": {"type": "string"},
#                     "date_posted": {"type": "string"},
#                     "description": {"type": "string"},
#                     "company": {"type": "string"},
#                     "apply_url": {"type": "string"}
#                 },
#                 "required": ["title", "location", "date_posted", "description", "apply_url"]
#             }
#         }
#     }
# }

# @router.post("/search")
# async def search_jobs(request: JobSearchRequest):
#     try:
#         # Modify our search query to explicitly include date filters IN THE QUERY itself
#         search_query = f"Machine Learning Engineer jobs posted in the last week site:linkedin.com OR site:indeed.com"
        
#         # Still use web search but with more explicit instructions
#         current_time = datetime.now().strftime("%B %d, %Y")
#         system_message = f"""Today is {current_time}. Find at least a minimum of 20 DIFFERENT real job postings matching the user's query. 
# It's critical that you return as many unique job listings as possible.

# You MUST return data in this exact format:
# {{"jobs": [
#   {{"title": "Actual Job Title", 
#    "company": "Real Company Name", 
#    "location": "Specific Location", 
#    "date_posted": "Specific Date", 
#    "description": "Actual job description text...", 
#    "apply_url": "https://real-application-url.com"}}
# ]}}

# IMPORTANT: You MUST include actual job listings with real data from your web search.
# If you can't find any jobs, explain why in your response outside the JSON.
# Do NOT return an empty array unless absolutely no jobs were found.
# """
        
#         # Make the API call to OpenAI
#         response = client.responses.create(
#             model="gpt-4o-mini",
#             tools=[{"type": "web_search_preview"}],
#             input=search_query,  # Date is in the query itself now
#             instructions=system_message
#         )
        
#         # Find the "message" type output regardless of its position
#         message_output = None
#         for output_item in response.output:
#             if hasattr(output_item, 'type') and output_item.type == 'message':
#                 message_output = output_item
#                 break
                
#         if not message_output or not hasattr(message_output, 'content') or not message_output.content:
#             raise ValueError("No message content found in response")
            
#         # Get text content from the message
#         text_content = message_output.content[0].text
        
#         # Clean up the text content to extract JSON
#         # Remove markdown code blocks
#         import re
#         json_text = text_content
        
#         # Remove markdown code formatting
#         json_text = re.sub(r'```json\s*|\s*```', '', json_text)
        
#         # Trim whitespace
#         json_text = json_text.strip()
        
#         print(f"RAW TEXT RESPONSE: {text_content}")
        
#         try:
#             # Try parsing the cleaned text as JSON
#             job_data = json.loads(json_text)
            
#             # Handle both a direct array or an object with a jobs property
#             if isinstance(job_data, list):
#                 jobs = job_data
#             else:
#                 jobs = job_data.get("jobs", [])
                
#         except json.JSONDecodeError:
#             # If that fails, try more aggressive extraction
#             try:
#                 # Find anything that looks like a JSON object or array
#                 json_pattern = r'(\{[\s\S]*\}|\[[\s\S]*\])'
#                 match = re.search(json_pattern, json_text)
                
#                 if match:
#                     json_candidate = match.group(0)
#                     job_data = json.loads(json_candidate)
                    
#                     if isinstance(job_data, list):
#                         jobs = job_data
#                     else:
#                         jobs = job_data.get("jobs", [])
#                 else:
#                     jobs = []
#             except:
#                 jobs = []
        
#         print("\n\nHERE ARE THE JOBS", jobs , "\n\n")
#         print("JOB LENGTH", len(jobs))

#         expanded_skills = expand_skills(request.primary_skills)
#         filtered_jobs, skillset = filter_jobs(jobs, expanded_skills,min_skills_match=3)

#         user_message = f"Search on job boards like Indeed, LinkedIn, and company career pages for: {search_query}. Find at least 10 job postings."

#         return {
#             "total_jobs_found": len(jobs),
#             "filtered_jobs_count": len(filtered_jobs),
#             "expanded_skills": skillset,
#             "jobs": filtered_jobs
#         }
        
                
#     except Exception as e:
        
#         print(f"Error searching for jobs: {str(e)}")
#         print(traceback.format_exc())
#         raise HTTPException(status_code=500, detail=f"Error searching for jobs: {str(e)}")
    
# # For testing purposes
# test_query = "software engineer jobs in United States"
    
# def search_jobs(request):
#     all_jobs = []
#     # Get first batch with initial query
#     jobs_batch_1 = execute_search(request.target_roles, request.preferred_location, "")
#     all_jobs.extend(jobs_batch_1)
    
#     # Get second batch with a slight variation
#     variation = "entry level" if "entry" not in " ".join(request.target_roles).lower() else "senior"
#     jobs_batch_2 = execute_search(request.target_roles, request.preferred_location, variation)
    
#     # Deduplicate based on URL or title+company
#     unique_jobs = remove_duplicates(all_jobs)
    
#     return {"jobs": unique_jobs}
    
