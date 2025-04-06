import logging
import sys
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Optional
from datetime import datetime, timedelta
# Assuming utils structure is accessible
from utils.supabase.db import supabase
from utils.supabase.supabase_utils import fetch_user_profile
from litellm import acompletion
import json
import asyncio

# Configure logger for this module
logger = logging.getLogger("career_insights")
logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

router = APIRouter()

# --- Implement the LLM call function ---
async def get_top_recent_gaps_from_llm(user_profile_text: str, recent_searches_summary: str) -> Dict:
    """
    Calls LLM to determine top 5 skill gaps based on recent history and user profile.

    Args:
        user_profile_text: The concatenated text of the user's resume.
        recent_searches_summary: A string summarizing recent target roles/queries and
                                 previously identified gaps from individual searches.

    Returns:
        A dictionary containing the top 5 overall skill gaps, e.g.,
        {'top_overall_gaps': [{'skill': '...', 'reason': '...'}]}
        Returns an empty dict on failure.
    """
    logger.info("Calling LLM for top 5 recent gaps analysis...")
    final_results = {"top_overall_gaps": []}

    try:
        prompt = f"""
        As a career advisor AI, analyze the user's profile and their recent job search activity to identify their **Top 5 most critical skill gaps**.

        **User Profile Summary (Resume Text):**
        ```
        {user_profile_text[:3000]}
        ```
        **(Resume truncated for brevity)**

        **Summary of Recent Job Search Activity (Last 7 Days):**
        ```
        {recent_searches_summary}
        ```

        **Analysis Task:**
        Based on the user's profile and their recent search targets (roles/queries) and the potential gaps identified in those searches, determine the **Top 5 skill areas** this user should focus on developing to best align with their recent job search patterns. Consider the frequency of required skills in their target roles and the skills repeatedly identified as gaps.

        For each of the Top 5 skills, provide:
        1.  The `skill` name.
        2.  A brief `reason` explaining why this skill is important based on the provided context (e.g., "Appears frequently in target roles like X", "Consistently identified gap for desired Y positions", "Essential for Z requirement mentioned often").

        **Output Format:**
        Respond ONLY with a valid JSON object with the following exact structure:
        {{
          "top_overall_gaps": [
            {{"skill": "Top Skill 1", "reason": "Reason 1"}},
            {{"skill": "Top Skill 2", "reason": "Reason 2"}},
            {{"skill": "Top Skill 3", "reason": "Reason 3"}},
            {{"skill": "Top Skill 4", "reason": "Reason 4"}},
            {{"skill": "Top Skill 5", "reason": "Reason 5"}}
          ]
        }}
        If fewer than 5 significant overall gaps are found, return fewer items in the list. If no significant gaps, return an empty list. Ensure the output is ONLY the JSON object.
        """

        response = await acompletion(
            model="gpt-4o", # Or your preferred model
            messages=[{
                "role": "system",
                "content": "You are a helpful career advisor AI synthesizing recent job search data to identify key skill gaps. Respond ONLY in the specified JSON format."
             },{
                 "role": "user",
                 "content": prompt
            }],
            response_format={ "type": "json_object" },
            max_tokens=600, # Increased slightly for reasoning
            temperature=0.4
        )

        # --- Parse the LLM response ---
        try:
            llm_output_text = response.choices[0].message.content.strip()
            parsed_output = json.loads(llm_output_text)
            # Validate structure
            if isinstance(parsed_output, dict) and "top_overall_gaps" in parsed_output and isinstance(parsed_output["top_overall_gaps"], list):
                # Further validate list items if needed
                valid_gaps = []
                for item in parsed_output["top_overall_gaps"]:
                    if isinstance(item, dict) and item.get("skill") and item.get("reason"):
                        valid_gaps.append(item)
                    else:
                        logger.warning(f"Skipping invalid item in top_overall_gaps: {item}")
                
                final_results["top_overall_gaps"] = valid_gaps
                logger.info(f"LLM identified {len(final_results['top_overall_gaps'])} overall top gaps.")
            else:
                logger.error(f"Overall gaps LLM output not in expected JSON structure: {llm_output_text}")

        except json.JSONDecodeError:
             logger.error(f"Failed to decode overall gaps LLM JSON output: {llm_output_text}")
        except Exception as parse_err:
             logger.error(f"Error parsing overall gaps LLM response: {str(parse_err)}")

    except Exception as e:
        logger.error(f"Error during LLM call for overall skill gap analysis: {str(e)}")
        # Return default empty structure on failure

    return final_results


@router.get("/insights/recent-skill-gaps/{user_id}")
async def get_recent_skill_gaps(user_id: str):
    """
    Analyzes job searches from the last 7 days for a user to find recurring skill gaps.
    """
    logger.info(f"Received request for recent skill gaps for user_id: {user_id}")

    try:
        # --- 1. Fetch recent searches (last 7 days) ---
        seven_days_ago = datetime.now() - timedelta(days=7)
        # Format for Supabase timestamp query (check your DB format, may need '.isoformat()')
        seven_days_ago_str = seven_days_ago.strftime('%Y-%m-%d %H:%M:%S')

        logger.info(f"Fetching searches since: {seven_days_ago_str}")
        
        # Wrap Supabase call in executor
        loop = asyncio.get_running_loop()
        search_history_result = await loop.run_in_executor(
            None,
            lambda: supabase.table("job_searches")
                       .select("query, consolidated_skill_gaps, target_roles") # Select relevant columns
                       .eq("user_id", user_id)
                       .gte("created_at", seven_days_ago_str) # Assumes 'created_at' column exists and is timestamp like
                       .execute()
        )
        
        recent_searches = search_history_result.data
        if not recent_searches:
            logger.info(f"No recent search history found for user {user_id} in the last 7 days.")
            return {"message": "No recent search history found to analyze.", "top_overall_gaps": []}

        logger.info(f"Found {len(recent_searches)} recent search records.")

        # --- 2. Fetch user profile ---
        # (Utility function already exists)
        user_profile_text = await fetch_user_profile(user_id)

        # --- 3. Aggregate Data for Prompt ---
        # Combine queries/roles and the saved consolidated gaps
        aggregated_queries = "; ".join([s.get('query', '') for s in recent_searches if s.get('query')])
        aggregated_roles = "; ".join([s.get('target_roles', '') for s in recent_searches if s.get('target_roles')])
        
        aggregated_gaps_list = []
        for search in recent_searches:
             gaps_data = search.get('consolidated_skill_gaps')
             # Check if gaps_data is a dict and has the 'top_gaps' key with a list
             if isinstance(gaps_data, dict) and isinstance(gaps_data.get('top_gaps'), list):
                 for gap in gaps_data['top_gaps']:
                      if isinstance(gap, dict) and gap.get('skill'): # Ensure gap is dict with skill
                          aggregated_gaps_list.append(f"- {gap['skill']} (Est: {gap.get('learn_time_estimate', 'N/A')})")

        aggregated_gaps_text = "\n".join(aggregated_gaps_list) if aggregated_gaps_list else "None previously identified."
        
        # Create a summary string (can be refined)
        recent_searches_summary = f"""
        Recent Target Roles/Queries: {aggregated_roles if aggregated_roles else aggregated_queries}
        Previously Identified Top Gaps (Consolidated per search):
        {aggregated_gaps_text}
        """

        # --- 4. Call LLM for Final Analysis ---
        # (Using placeholder function for now)
        final_analysis = await get_top_recent_gaps_from_llm(user_profile_text, recent_searches_summary)

        # --- 5. Return Result ---
        return final_analysis

    except HTTPException as he:
         logger.error(f"HTTP Exception fetching recent gaps for user {user_id}: {he.detail}")
         raise he # Re-raise FastAPI exceptions
    except Exception as e:
        logger.error(f"Unexpected error fetching recent gaps for user {user_id}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal server error analyzing recent skill gaps: {str(e)}")

# --- Include this router in api/main.py ---
