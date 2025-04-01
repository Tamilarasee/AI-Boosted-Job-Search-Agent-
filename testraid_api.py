import requests

url = "https://linkedin-job-search-api.p.rapidapi.com/active-jb-7d"

querystring = {"limit":"1","offset":"0","title_filter":"\"Data Engineer\"","location_filter":"\"United States\" OR \"United Kingdom\""}

headers = {
	"x-rapidapi-key": "cded3f121emsh2724131035ba867p1f62c6jsn16c0d2cc37f6",
	"x-rapidapi-host": "linkedin-job-search-api.p.rapidapi.com"
}

response = requests.get(url, headers=headers, params=querystring)

print(response.json())