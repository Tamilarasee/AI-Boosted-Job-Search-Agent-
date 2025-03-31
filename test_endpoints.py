import requests

# API key that seemed to work in your test file
api_key = "4f01c46da8msh7d463eca7aa8a34p1aa222jsn1a6f7252fcbe"

# Common headers and query parameters
headers = {
    "x-rapidapi-key": api_key,
    "x-rapidapi-host": "linkedin-job-search-api.p.rapidapi.com"
}

querystring = {
    "limit": "1",
    "offset": "0",
    "title_filter": "\"Data Engineer\"",
    "location_filter": "\"United States\""
}

# Test the "jobs" endpoint
print("\nTesting the /jobs endpoint:")
try:
    jobs_url = "https://linkedin-job-search-api.p.rapidapi.com/jobs"
    response = requests.get(jobs_url, headers=headers, params=querystring)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text[:200]}...")  # First 200 chars
except Exception as e:
    print(f"Error: {str(e)}")

# Test the "active-jb-7d" endpoint
print("\nTesting the /active-jb-7d endpoint:")
try:
    active_url = "https://linkedin-job-search-api.p.rapidapi.com/active-jb-7d"
    response = requests.get(active_url, headers=headers, params=querystring)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text[:200]}...")  # First 200 chars
except Exception as e:
    print(f"Error: {str(e)}") 