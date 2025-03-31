import requests
import json
from datetime import datetime

url = "https://api.tavily.com/search"

current_date = datetime.now().strftime("%B %d, %Y")

payload = {
    "query": f"Machine learning engineer jobs in United States posted in the last 7 days. Today is {current_date}. Bring only job postings with a apply url, no general content like articles or reviews.",
    "topic": "general",
    "search_depth": "advanced",
    "chunks_per_source": 3,
    "max_results": 100,
    "time_range": "week",
    "days": 7,
    "include_answer": True,
    "include_raw_content": False,
    "include_images": False,
    "include_image_descriptions": False,
    "include_domains": ["linkedin.com", "indeed.com", "glassdoor.com", "monster.com", "ziprecruiter.com"],
    "exclude_domains": []
}

headers = {
    "Authorization": "Bearer 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",
    "Content-Type": "application/json"
}

response = requests.request("POST", url, json=payload, headers=headers)

# Parse the JSON response
result = response.json()

# Print the formatted JSON output
print(json.dumps(result, indent=2))

# Extract and format job listings if available
if "results" in result:
    print(f"\nFound {len(result['results'])} job listings:")
    
    # Print a summary of the results
    for i, job in enumerate(result["results"], 1):
        print(f"\nJob {i}: {job.get('title', 'No title')}")
        print(f"URL: {job.get('url', 'No URL')}")
        print(f"Website: {job.get('source', 'Unknown website')}")
        
        # Extract content to look for date and description
        content = job.get('content', '')
        
        # Try to find posting date in content (simplified approach)
        date_posted = "Unknown date"
        date_indicators = ["Posted on", "Date posted", "Posted", "Date:"]
        for indicator in date_indicators:
            if indicator in content:
                start_idx = content.find(indicator) + len(indicator)
                end_idx = content.find(".", start_idx)
                if end_idx > start_idx:
                    date_posted = content[start_idx:end_idx].strip()
                    break
        
        print(f"Date Posted: {date_posted}")
        
        # Print a shortened version of the content as description
        description = content[:300] + "..." if len(content) > 300 else content
        print(f"Description: {description}")