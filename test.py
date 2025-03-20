from openai import OpenAI
client = OpenAI()

completion = client.chat.completions.create(
    model="gpt-4o-search-preview",
    web_search_options={
        "user_location": {
            "type": "approximate",
            "approximate": {
                "country": "US",
                "city": "Chicago",
                "region": "Illinois",
            }
        },
    },
    messages=[{
        "role": "user",
        "content": """
What is the best Job API avaialble for use today - it should include jobs from indeed and linkedin - with most uptodate data
"""
  }],
)

print(completion.choices[0].message.content)