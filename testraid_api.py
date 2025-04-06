import requests

url = "https://linkedin-job-search-api.p.rapidapi.com/active-jb-7d"

querystring = {"limit":"1","offset":"0","title_filter":"\"Data Engineer\"","location_filter":"\"United States\" OR \"United Kingdom\""}

headers = {
	"x-rapidapi-key": "8e2898eeffmsh9725adeabfc7c63p143618jsn552c1722ee91",
	"x-rapidapi-host": "linkedin-job-search-api.p.rapidapi.com"
}

response = requests.get(url, headers=headers, params=querystring)

print(response.json())