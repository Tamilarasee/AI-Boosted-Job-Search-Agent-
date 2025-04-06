from fastapi import HTTPException
from pydantic import BaseModel, ValidationError, Field
from typing import List, Optional, Dict
import logging
import sys
from litellm import acompletion
from dotenv import load_dotenv
from pinecone import Pinecone
import os
import asyncio
from utils.pinecone.vector_db import index as pinecone_index


load_dotenv()

# Configure logger
logger = logging.getLogger("pinecone_search")
logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


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
            model="gpt-4o",  
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

def search_pinecone_jobs(query: str, top_k: int = 10):
    """Search for jobs in Pinecone using the optimized query (with dynamic init and pre-search stats check)"""
    logger = logging.getLogger(__name__)
    logger.warning("!!! DEBUG: Initializing Pinecone client inside search_pinecone_jobs !!!")
    local_pinecone_index = None # Define variable outside try block

    try:
        # --- Dynamic Initialization ---
        pinecone_api_key = os.getenv("PINECONE_API_KEY")
        if not pinecone_api_key: raise ValueError("PINECONE_API_KEY missing")
        pc = Pinecone(api_key=pinecone_api_key)
        index_name = "job-search-tool"
        local_pinecone_index = pc.Index(index_name)
        logger.info(f"Dynamically initialized index object: {local_pinecone_index}")
        # --- End Dynamic Initialization ---

        # --- DIAGNOSTIC: Check Index Stats BEFORE Searching ---
        try:
            stats = local_pinecone_index.describe_index_stats()
            logger.info(f"!!! DEBUG: Index stats BEFORE search: {stats}")
            namespace_stats = stats.namespaces.get("job-list")
            if namespace_stats:
                 logger.info(f"!!! DEBUG: Vector count in 'job-list' namespace BEFORE search: {namespace_stats.vector_count}")
            else:
                 logger.warning("!!! DEBUG: Namespace 'job-list' not found in stats BEFORE search.")
        except Exception as stats_err:
            logger.error(f"!!! DEBUG: Error getting index stats before search: {stats_err}")
        # --- END DIAGNOSTIC ---

        logger.info(f"Preparing Pinecone search for query: {query}...")
        

        # Use the locally initialized index object for the search
        results = local_pinecone_index.search( 
            namespace="job-list",
            query={
                "inputs": {"text": query},
                "top_k": top_k
            },
            fields=["_id","_score"])

        logger.info(f"Pinecone search (dynamic init) raw results: {results}")

        return results

    except Exception as e:
        # ... (keep error handling) ...
        logger.error(f"Error querying Pinecone (dynamic init): {str(e)}")
        return {'error': str(e)}

async def delete_pinecone_namespace_vectors(namespace: str):
    """Deletes all vectors within a specific namespace in Pinecone (with dynamic init)."""
    logger = logging.getLogger(__name__)
    logger.warning("!!! DEBUG: Initializing Pinecone client inside delete_pinecone_namespace_vectors !!!")

    try:
        # --- Dynamic Initialization ---
        pinecone_api_key = os.getenv("PINECONE_API_KEY")
        if not pinecone_api_key: raise ValueError("PINECONE_API_KEY missing")
        pc = Pinecone(api_key=pinecone_api_key)
        index_name = "job-search-tool"
        local_pinecone_index = pc.Index(index_name)
        logger.info(f"Dynamically initialized index object for delete: {local_pinecone_index}")
        # --- End Dynamic Initialization ---

        # Check if namespace exists first using the local index
        response = local_pinecone_index.describe_index_stats()
        if namespace not in response['namespaces']:
            logger.info(f"Namespace '{namespace}' does not exist in Pinecone, nothing to delete")
            return
            
    except Exception as e:
        logger.error(f"Error checking namespace existence (dynamic init): {str(e)}")
        # Don't raise, but log that we couldn't confirm existence/deletion
        return

    # Proceed with delete if namespace check didn't fail catastrophically
    logger.warning(f"Attempting to delete all vectors in Pinecone namespace: {namespace}")
    try:
        # Use delete with 'deleteAll=True' for the namespace using the local index
        delete_response = local_pinecone_index.delete(delete_all=True, namespace=namespace)
        logger.info(f"Pinecone delete response for namespace '{namespace}': {delete_response}")
        # Optional small delay
        # await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"Error deleting vectors from Pinecone namespace '{namespace}' (dynamic init): {str(e)}")
        # Don't raise HTTPException from here, let orchestrator handle potential downstream issues
        # Maybe return a flag indicating failure? For now, just log.


# --- Define Pydantic Model for Supabase Job Records ---
# Adjust field types based on your actual Supabase table schema
class SupabaseJobRecord(BaseModel):
    id: int
    search_id: Optional[int] = None # Add other fields from your table
    title: Optional[str] = ""
    company: Optional[str] = ""
    location: Optional[str] = ""
    description: str # Make description mandatory for embedding
    url: Optional[str] = ""
    date_posted: Optional[str] = ""
    job_type: Optional[str] = ""
    skills_matched: Optional[str] = ""
    total_skills: Optional[int] = 0
    created_at: Optional[str] = None # Assuming it's stored as text, adjust if datetime

    # Allow extra fields fetched from Supabase but not explicitly defined
    class Config:
        extra = 'allow'


async def sync_jobs_to_pinecone_utility(jobs_to_sync: List[Dict], namespace: str = "job-list"):
    """
    Takes a list of job dictionaries (from Supabase), validates them,
    and upserts them to Pinecone (with dynamic init).
    """
    logger = logging.getLogger(__name__)
    logger.warning("!!! DEBUG: Initializing Pinecone client inside sync_jobs_to_pinecone_utility !!!")

    if not jobs_to_sync:
        logger.info("No jobs provided to sync_jobs_to_pinecone_utility.")
        return {"status": "no_data", "message": "No jobs to sync", "count": 0}

    logger.info(f"Preparing {len(jobs_to_sync)} jobs for Pinecone upsert into namespace '{namespace}'...")
    records = []
    successful_preparation_count = 0
    validation_errors = 0

    for job_dict in jobs_to_sync:
        try:
            # --- Validate the incoming dictionary against the Pydantic model ---
            validated_job = SupabaseJobRecord(**job_dict)

            # Ensure essential fields (after validation) are present
            # 'description' is mandatory in the model, 'id' is implicitly checked by Pydantic
            if not validated_job.description:
                 logger.warning(f"Skipping job ID {validated_job.id} due to missing description after validation.")
                 validation_errors += 1
                 continue

            # Create a unique ID for Pinecone using the validated job's Supabase ID
            pinecone_id = f"job_{validated_job.id}"

            # Prepare the record using validated data
            record = {
                "id": pinecone_id,
                "text": validated_job.description, # Text to be embedded by Pinecone
                "title": validated_job.title or "", # Use validated attributes
                "company": validated_job.company or "",
                "location": validated_job.location or "",
                "url": validated_job.url or "",
                "job_type": validated_job.job_type or "",
                "date_posted": validated_job.date_posted or "",
                "skills_matched": validated_job.skills_matched or ""
                # Add any other relevant metadata fields using validated_job.field_name
            }
            records.append(record)
            successful_preparation_count += 1

        except ValidationError as val_err:
            logger.warning(f"Skipping job due to validation error: {val_err}. Original data: {job_dict.get('id', 'N/A')}")
            validation_errors += 1
            continue # Skip this job if validation fails

        except Exception as prep_err:
             logger.error(f"Error preparing job ID {job_dict.get('id', 'N/A')} for Pinecone: {str(prep_err)}")
             # Optionally count this as a different type of error
             continue # Skip this job on preparation error


    if validation_errors > 0:
        logger.warning(f"{validation_errors} jobs skipped due to validation errors.")

    if not records:
         logger.warning("No valid records could be prepared for Pinecone upsert after validation.")
         return {"status": "prep_failed", "message": "No valid records to upsert", "count": 0, "validation_errors": validation_errors}

    # --- Upsert Logic with Dynamic Init ---
    logger.info(f"Attempting to upsert {len(records)} prepared records to Pinecone namespace '{namespace}'...")
    try:
        # --- Dynamic Initialization (Same as in search function) ---
        pinecone_api_key = os.getenv("PINECONE_API_KEY")
        if not pinecone_api_key:
            raise ValueError("PINECONE_API_KEY environment variable not found.")
        pc = Pinecone(api_key=pinecone_api_key)
        index_name = "job-search-tool"
        local_pinecone_index = pc.Index(index_name)
        logger.info(f"Dynamically initialized index object for sync: {local_pinecone_index}")
        # --- End Dynamic Initialization ---

        # Perform the upsert operation using the local index object
        # Ensure 'upsert_records' is the correct method for your client version
        upsert_response = local_pinecone_index.upsert_records(
             records=records,
             namespace=namespace
        )
        

        logger.info(f"Successfully upserted {len(records)} jobs to Pinecone namespace '{namespace}'. Response: {upsert_response}")
        # Add delay to allow Pinecone index to update
        await asyncio.sleep(5)
        logger.info(f"!!! DEBUG: Index stats AFTER upsert: {local_pinecone_index.describe_index_stats()}")
        return {
            "status": "success",
            "message": f"Successfully synced {len(records)} jobs to Pinecone ({validation_errors} skipped validation)",
            "pinecone_response": upsert_response,
            "count": len(records),
            "validation_errors": validation_errors
        }
    except Exception as e:
        logger.error(f"Error upserting to Pinecone namespace '{namespace}': {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error upserting jobs to Pinecone: {str(e)}"
        )
