from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import logging
import sys
from utils.supabase.db import supabase
from litellm import completion, acompletion
from dotenv import load_dotenv
from utils.pinecone.vector_db import index as pinecone_index
import asyncio
import json

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

async def generate_optimized_query(search_context: dict) -> str:
    """Generate an optimized search query using LLM"""
    try:
        prompt = f"""
        Given a job seeker's resume and preferences, create an optimized search query.
        
        Resume text: {search_context['resume_text']}
        
        Job preferences:
        - Target roles: {', '.join(search_context['target_roles'])}
        - Primary skills: {', '.join(search_context['primary_skills'])}
        - Location: {search_context['location']}
        - Job type: {search_context['job_type']}
        - Additional preferences: {search_context['additional_preferences']}
        
        Create a concise, relevant search query that captures the essential requirements and preferences.
        Focus on key skills, experience level, and job requirements that match the resume.
        """
        
        response = await acompletion(
            model="gpt-4o-mini",  
            messages=[{
                "role": "system",
                "content": "You are a job search expert that creates optimized search queries."
            }, {
                "role": "user",
                "content": prompt
            }],
            max_tokens=300
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"Error generating optimized query: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate search query"
        )

async def search_pinecone_jobs(query: str, top_k: int = 10):
    """Search for jobs in Pinecone using the optimized query"""
    try:
        # Using Pinecone's correct query format
        results = pinecone_index.search(
            namespace="job-list",
            query={
                "inputs": {"text": query},
                "top_k": top_k
            },
            fields=["_id","_score"]  
        )
        
        return results
        
    except Exception as e:
        logger.error(f"Error querying Pinecone: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to search jobs in database"
        )

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

async def analyze_job_fit_and_provide_tips(user_profile_text: str, job_details: dict) -> dict:
    """
    Analyzes the fit between a user's profile and a specific job, providing actionable insights.

    Args:
        user_profile_text: The concatenated text of the user's resume.
        job_details: A dictionary containing details of a single job 
                     (should include 'title', 'company', 'description', etc.).

    Returns:
        A dictionary containing the analysis results (missing skills, learning time, tips).
        Returns an empty dict if analysis fails.
    """
    logger.info(f"Analyzing job fit for job ID {job_details.get('id', 'N/A')} and user...")
    
    # Default structure for results
    analysis_results = {
        "missing_skills": [], # Will be list of {"skill": "...", "learn_time_estimate": "..."}
        "resume_suggestions": {
            "highlight": [],
            "consider_removing": []
        }
    }

    try:
        # --- Step 3: Construct Prompt and Call LLM ---
        job_description = job_details.get('description', '')
        job_title = job_details.get('title', 'this job')
        
        # Ensure we have necessary details to proceed
        if not user_profile_text or not job_description:
             logger.warning(f"Missing user profile or job description for job {job_details.get('id', 'N/A')}. Skipping analysis.")
             return {} # Return empty if essential info is missing

        prompt = f"""
        Analyze the alignment between the provided User Profile (Resume) and the Job Description.
        Identify skill gaps and provide resume tailoring suggestions.

        **User Profile (Resume Text):**
        ```
        {user_profile_text} 
        ```
        **(Resume truncated to first 3000 chars if longer)**

        **Job Description for "{job_title}":**
        ```
        {job_description[:4000]}
        ```
        **(Job Description truncated to first 4000 chars if longer)**

        **Analysis Tasks:**

        1.  **Identify Top 3 Missing Skills:** List the top 3 most important skills or qualifications mentioned in the Job Description that are NOT present in the User Profile. The user might have written that skill in abbreviation or in any other way in the resume. Look out carefully.
        2.  **Estimate Learning Time for Each Missing Skill:** For EACH missing skill identified above, estimate the time needed for this specific user (considering their existing profile) to learn it sufficiently to complete a relevant project or earn a certification. 
        State the estimate clearly (e.g., "2-4 weeks, 2 hours per day (project focus)", "1 month, 2 hours per day (certification focus)").
        Also provide a short one liner of example projects or certifications that the user can do to learn the skill.
            
        3.  **Provide Resume Tailoring Suggestions:**
            *   **Highlight:** List 2-3 specific skills or experiences ALREADY MENTIONED but NOT highlighted in the User Profile that are particularly relevant to this Job Description and should be emphasized. Do not include if they have emphasized it enough in the resume. If it is not well written, suggest how to write it better or say that it is not well written.
            *   **Consider Removing:** List 1-2 items in the User Profile that seem LEAST relevant to this specific job and could potentially be removed to make space for more relevant points. Be cautious and phrase as suggestions.

        **Output Format:**
        Please provide the response ONLY as a valid JSON object with the following exact structure:
        {{
          "missing_skills": [
            {{"skill": "Example Skill 1", "learn_time_estimate": "Example Time 1"}},
            {{"skill": "Example Skill 2", "learn_time_estimate": "Example Time 2"}},
            {{"skill": "Example Skill 3", "learn_time_estimate": "Example Time 3"}}
          ],
          "resume_suggestions": {{
            "highlight": ["Example Highlight 1", "Example Highlight 2"],
            "consider_removing": ["Example Removal Suggestion 1"]
          }}
        }}
        Ensure the output is ONLY the JSON object, without any introductory text or explanations.
        """

        # Use the asynchronous version: acompletion
        response = await acompletion(
            model="gpt-4o-mini", 
            messages=[{
                "role": "system", 
                "content": "You are a helpful career advisor AI analyzing job fit and providing actionable advice. Respond ONLY in the specified JSON format."
             },{
                 "role": "user", 
                 "content": prompt
            }],
            response_format={ "type": "json_object" }, # Enforce JSON output if model supports it
            max_tokens=500, # Adjust as needed
            temperature=0.5 # Adjust for creativity vs consistency
        )

        # --- Parse the LLM response ---
        try:
            llm_output_text = response.choices[0].message.content.strip()
            # Attempt to parse the JSON
            parsed_output = json.loads(llm_output_text)
            
            # Basic validation (can be made more robust)
            if isinstance(parsed_output, dict) and \
               "missing_skills" in parsed_output and \
               "resume_suggestions" in parsed_output:
                analysis_results = parsed_output
            else:
                 logger.error(f"LLM output for job {job_details.get('id', 'N/A')} is not in expected JSON structure: {llm_output_text}")
                 # Keep default empty results

        except json.JSONDecodeError:
            logger.error(f"Failed to decode LLM JSON output for job {job_details.get('id', 'N/A')}: {llm_output_text}")
            # Keep default empty results
        except Exception as parse_err:
             logger.error(f"Error parsing LLM response for job {job_details.get('id', 'N/A')}: {str(parse_err)}")
             # Keep default empty results

    except Exception as e:
        logger.error(f"Error during LLM call for job fit analysis (Job ID {job_details.get('id', 'N/A')}): {str(e)}")
        # Return default empty structure on failure
        return {} # Returning the default structure defined at the start

    logger.info(f"Analysis complete for job ID {job_details.get('id', 'N/A')}")
    return analysis_results

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

