from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import logging
import sys
from utils.supabase.db import supabase
from litellm import completion
from dotenv import load_dotenv
from utils.pinecone.vector_db import index as pinecone_index

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
        
        response = completion(
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
    
    # Format results for UI display
    formatted_results = [{
        **job,
        'match_percentage': round(job['similarity_score'] * 100, 1),  # Convert score to percentage
        'match_text': f"{round(job['similarity_score'] * 100)}% Match"  # Ready-to-display text
    } for job in complete_job_results]
    
    return {
        "status": "success",
        "query": optimized_query,
        "results": formatted_results,
        "total_results": len(formatted_results)
    }

# Add helper functions below (e.g., for fetching resume, calling LLM, querying Pinecone)
