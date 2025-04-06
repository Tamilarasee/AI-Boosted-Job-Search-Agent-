import logging
import sys
from litellm import acompletion
from dotenv import load_dotenv
import json
from typing import List, Dict


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
        {job_description}
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

async def consolidate_skill_gaps(user_profile_text: str, all_analysis_results: List[Dict]) -> Dict:
    """
    Analyzes a list of individual job analyses to find the top 3 consolidated skill gaps.

    Args:
        user_profile_text: The concatenated text of the user's resume.
        all_analysis_results: A list of dictionaries, where each dictionary is the
                              output of analyze_job_fit_and_provide_tips for a single job.

    Returns:
        A dictionary containing the top 3 consolidated gaps, e.g.,
        {'top_gaps': [{'skill': '...', 'learn_time_estimate': '...'}]}
        Returns an empty dict if consolidation fails or no skills found.
    """
    logger.info("Starting consolidation of skill gaps...")
    consolidated_results = {"top_gaps": []}
    
    # --- 1. Aggregate all missing skills ---
    all_missing_skills_details = []
    for analysis in all_analysis_results:
        # Ensure the analysis dict and missing_skills list exist and are valid
        if isinstance(analysis, dict) and "missing_skills" in analysis and isinstance(analysis["missing_skills"], list):
             all_missing_skills_details.extend(analysis["missing_skills"])

    if not all_missing_skills_details:
        logger.info("No missing skills found across analyzed jobs to consolidate.")
        return consolidated_results # Return empty if no skills to process

    # Optional: Add frequency count here if desired, but LLM can infer from repetition too
    # skill_counts = {}
    # for item in all_missing_skills_details:
    #     skill_name = item.get('skill')
    #     if skill_name:
    #         skill_counts[skill_name] = skill_counts.get(skill_name, 0) + 1
    
    # Format for prompt (just list them out)
    missing_skills_text = "\n".join([f"- {item.get('skill', 'N/A')} (Est: {item.get('learn_time_estimate', 'N/A')})" for item in all_missing_skills_details])

    # --- 2. Construct Prompt and Call LLM ---
    try:
        prompt = f"""
        Analyze the following list of potential skill gaps identified across multiple job applications for the user profile provided below.

        **User Profile (Resume Text):**
        ```
        {user_profile_text}
        ```
        **(Resume truncated)**

        **List of Potential Skill Gaps from Job Analyses:**
        ```
        {missing_skills_text}
        ```

        **Task:**
        Identify the **Top 3 most impactful or frequently recurring skill gaps** from the list above that this user should prioritize learning to improve their job prospects, considering their existing profile. For each of these Top 3 skills:
        1.  State the skill name clearly.
        2.  Provide a concise, synthesized learning time estimate (e.g., "Approx. 3-5 weeks project focus", "Around 1 month for certification") based on the estimates provided and the user's profile. Include a brief example project/cert idea.

        **Output Format:**
        Respond ONLY with a valid JSON object with the following structure:
        {{
          "top_gaps": [
            {{"skill": "Consolidated Skill 1", "learn_time_estimate": "Consolidated Estimate 1 with project/cert idea"}},
            {{"skill": "Consolidated Skill 2", "learn_time_estimate": "Consolidated Estimate 2 with project/cert idea"}},
            {{"skill": "Consolidated Skill 3", "learn_time_estimate": "Consolidated Estimate 3 with project/cert idea"}}
          ]
        }}
        If fewer than 3 significant recurring gaps are found, return fewer items in the list. If no significant gaps, return an empty list. Ensure the output is ONLY the JSON object.
        """

        response = await acompletion(
            model="gpt-4o", # Or preferred model
            messages=[{
                "role": "system",
                "content": "You are a helpful career advisor AI summarizing key skill gaps for a user. Respond ONLY in the specified JSON format."
             },{
                 "role": "user",
                 "content": prompt
            }],
            response_format={ "type": "json_object" },
            max_tokens=400, # Adjust as needed
            temperature=0.4
        )

        # --- 3. Parse Response ---
        try:
            llm_output_text = response.choices[0].message.content.strip()
            parsed_output = json.loads(llm_output_text)
            # Validate structure
            if isinstance(parsed_output, dict) and "top_gaps" in parsed_output and isinstance(parsed_output["top_gaps"], list):
                consolidated_results = parsed_output
                logger.info(f"Consolidated top gaps identified: {len(consolidated_results['top_gaps'])}")
            else:
                logger.error(f"Consolidated skills LLM output not in expected JSON structure: {llm_output_text}")

        except json.JSONDecodeError:
             logger.error(f"Failed to decode consolidated skills LLM JSON output: {llm_output_text}")
        except Exception as parse_err:
             logger.error(f"Error parsing consolidated skills LLM response: {str(parse_err)}")

    except Exception as e:
        logger.error(f"Error during LLM call for skill gap consolidation: {str(e)}")
        # Return default empty structure on failure

    return consolidated_results
