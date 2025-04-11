import requests

url = "https://linkedin-job-search-api.p.rapidapi.com/active-jb-7d"

querystring = {"limit":"1","offset":"0","title_filter":"\"Data Engineer\"","location_filter":"\"United States\" OR \"United Kingdom\""}

headers = {
	"x-rapidapi-key": "",
	"x-rapidapi-host": "linkedin-job-search-api.p.rapidapi.com"
}

response = requests.get(url, headers=headers, params=querystring)

print(response.json())