from openai import OpenAI

client = OpenAI()
# import openai
# print(openai.__version__)

response = client.responses.create(
    model="gpt-4o",
    tools=[{ "type": "web_search_preview" }],
    input="100 Machine learning engineer jobs in USA posted in the last 7 days",
)

print(response)
