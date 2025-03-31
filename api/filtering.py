import json
from openai import OpenAI

client = OpenAI()

def expand_skills(skills):
    """Expand each skill to related keywords the LLM might recognize"""
    skill_prompt = f"""
    INSTRUCTIONS:
    1. For each of these skills, provide 10-15 terms inferring them from the skill that might appear in most job descriptions:
    {', '.join(skills)}. 
    2. The first term should be the skill itself. 
    3. Abbreviations/expansions of the skill should be included.
    4. The later terms should not contain the same words as the skill. 
    5. Make sure each term is distinct and doesn't overlap with the main skill name.
         
    Format your response as a JSON object where each skill is a key with an array of related terms.
    """
    
    skill_response = client.responses.create(
        model="gpt-4o-mini",
        input=skill_prompt        
    )
    
    # Find the "message" type output regardless of position
    message_output = None
    for output_item in skill_response.output:
        if hasattr(output_item, 'type') and output_item.type == 'message':
            message_output = output_item
            break
            
    if not message_output or not hasattr(message_output, 'content') or not message_output.content:
        raise ValueError("No message content found in response")
        
    # Get text content from the message
    text_content = message_output.content[0].text
    print(f"\n\nTEXT CONTENT expanded skills: {text_content}\n\n")
    # Clean up JSON
    import re
    json_text = text_content
    json_text = re.sub(r'```json\s*|\s*```', '', json_text)
    json_text = json_text.strip()
    
    try:
        expanded_skills = json.loads(json_text)
    except json.JSONDecodeError:
        # Try more aggressive extraction
        try:
            json_pattern = r'(\{[\s\S]*\})'
            match = re.search(json_pattern, json_text)
            
            if match:
                expanded_skills = json.loads(match.group(0))
            else:
                expanded_skills = {skill: [skill] for skill in skills}
        except:
            expanded_skills = {skill: [skill] for skill in skills}
    
    return expanded_skills

def skills_match_count(job_description, expanded_skills):
    """Count how many of the user's skills appear in the job description"""
    description_lower = job_description.lower()
    
    skillset = {}

    for skill, related_terms in expanded_skills.items():
        matched_skills = set()

        for term in related_terms:
            if term.lower() in description_lower:
                matched_skills.add(term)
            # try to split words in the term and check them for better results
            if matched_skills:
                skillset[skill] = list(matched_skills)
        
  
    return skillset

def filter_jobs(jobs, expanded_skills, min_skills_match=3):
    """Filter jobs based on skills matches"""
    filtered_jobs = []
    
    for job in jobs:
        skillset = skills_match_count(job["description"], expanded_skills)
        
        if len(skillset) >= min_skills_match:
            # Add match information to the job
            job["skills_match_count"] = sum(len(related_skills) for related_skills in skillset.values())
            job["job_matched_skills"] = skillset
            filtered_jobs.append(job)
    
    # Sort by number of skills matched (descending)
    filtered_jobs.sort(key=lambda x: x["skills_match_count"], reverse=True)
    
    #Try to do half of the maximum match score as well
    # If there are more matches we can filter by job type as well

    # Limit to top 100 matches
    return filtered_jobs[:100], skillset
