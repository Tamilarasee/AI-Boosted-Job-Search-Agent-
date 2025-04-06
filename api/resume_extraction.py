from pypdf import PdfReader
from io import BytesIO
import logging
import sys
from litellm import acompletion
from dotenv import load_dotenv
import json
from typing import Dict, List


def extract_pdf_text(file_object):
    try:
        reader = PdfReader(file_object)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"PDF extraction error: {str(e)}\n{error_details}")
        raise Exception(f"Error extracting PDF text: {str(e)}")


load_dotenv()

# Configure logger
logger = logging.getLogger("profile_analysis")
logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def extract_titles_and_skills(resume_text: str) -> Dict[str, List[str]]:
    """
    Uses LLM to extract top 5 suggested job titles and key skills from resume text.

    Args:
        resume_text: The full text content of the user's resume(s).

    Returns:
        A dictionary like {"titles": ["Title1", ...], "skills": ["Skill1", ...]}
        Returns empty lists if extraction fails.
    """
    logger.info(f"Starting title/skill extraction for resume (length: {len(resume_text)})...")
    results = {"titles": [], "skills": []}
    if not resume_text:
        return results

    try:
        prompt = f"""
        Analyze the following resume text and identify the most relevant information for a job search.

        **Resume Text:**
        ```
        {resume_text[:8000]} 
        ```
        **(Resume truncated if very long)**

        **Tasks:**
        1.  **Identify Top 5 Job Titles:** Based *only* on the experience, skills, and projects described in the resume, list the Top 5 most suitable job titles this person could realistically target. Be specific (e.g., "Senior Backend Engineer (Python)", "Machine Learning Scientist", "Cloud Infrastructure Engineer").
        2.  **Extract Key Skills:** List the most prominent and frequently mentioned technical skills, tools, programming languages, and methodologies from the resume text. Aim for around 10-15 key skills.

        **Output Format:**
        Respond ONLY with a valid JSON object with the following exact structure:
        {{
          "titles": ["Job Title 1", "Job Title 2", "Job Title 3", "Job Title 4", "Job Title 5"],
          "skills": ["Skill 1", "Skill 2", "Skill 3", ...]
        }}
        Ensure the output is ONLY the JSON object.
        """

        response = await acompletion(
            model="gpt-4o-mini", # A capable but cheaper model often suffices here
            messages=[{
                "role": "system",
                "content": "You are an expert resume analyzer assisting job seekers. Extract relevant job titles and skills. Respond ONLY in the specified JSON format."
             },{
                 "role": "user",
                 "content": prompt
            }],
            response_format={ "type": "json_object" },
            max_tokens=400, # Adjust as needed
            temperature=0.2 # Low temp for factual extraction
        )

        # Parse response
        try:
            llm_output_text = response.choices[0].message.content.strip()
            parsed_output = json.loads(llm_output_text)
            if isinstance(parsed_output, dict) and \
               isinstance(parsed_output.get('titles'), list) and \
               isinstance(parsed_output.get('skills'), list):
                results = parsed_output
                logger.info(f"Successfully extracted {len(results['titles'])} titles and {len(results['skills'])} skills.")
            else:
                logger.error(f"LLM extraction output not in expected structure: {llm_output_text}")
        except Exception as parse_err:
             logger.error(f"Error parsing LLM extraction response: {str(parse_err)}")

    except Exception as e:
        logger.error(f"Error during LLM call for title/skill extraction: {str(e)}")

    return results


