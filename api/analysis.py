import logging
import sys
from litellm import acompletion
from dotenv import load_dotenv
import json


load_dotenv()

# Configure logger
logger = logging.getLogger("pinecone_search")
logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')




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

        1.  **Identify Top 3 Missing Skills:** List the top 3 most important skills or qualifications mentioned in the Job Description that are NOT present in the User Profile. The user might have written that skill in abbreviation (like ELK which includes Elasticsearch, Logstash and Kibana), or in any other way in the resume. Look out carefully.
        2.  **Estimate Learning Time for Each Missing Skill:** For EACH missing skill identified above, estimate the time needed for this specific user (considering their existing profile) to learn it sufficiently to complete a relevant project or earn a certification. 
        State the estimate clearly (e.g., "2-4 weeks, 2 hours per day (project focus)", "1 month, 2 hours per day (certification focus)").
        Also provide a short one liner of example projects or certifications that the user can do to learn the skill.
            
        3.  **Provide Resume Tailoring Suggestions:**
            *   **Highlight:** List 2-3 specific skills or experiences ALREADY MENTIONED but NOT highlighted in the User Profile that are particularly relevant to this Job Description and should be emphasized. Do not include if they have emphasized it enough in the resume. If it is not well written, suggest how to write it better or say that it is not well written.
            *   **Consider Removing:** List 1-2 items in the User Profile that seem LEAST relevant to this specific job and could potentially be removed to make space for more relevant points. Be cautious and phrase as suggestions.

        If you do not have a good suggestion, just say "No suggestions" for that field. Dont make up something.
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
            model="gpt-4o", 
            messages=[{
                "role": "system", 
                "content": "You are a helpful career advisor AI analyzing job fit and providing actionable advice. Respond ONLY in the specified JSON format."
             },{
                 "role": "user", 
                 "content": prompt
            }],
            response_format={ "type": "json_object" }, # Enforce JSON output if model supports it
            max_tokens=500, # Adjust as needed
            temperature=0.3 # Adjust for creativity vs consistency
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
