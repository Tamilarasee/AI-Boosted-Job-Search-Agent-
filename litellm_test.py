# from litellm import completion
# import os
# from dotenv import load_dotenv

# load_dotenv()

# ## set ENV variables
# # load_dotenv() sends the API key to the environment variable automatically
# #litellm automatically looks for OPENAI_API_KEY in your environment variables
# response = completion(
#   model="openai/gpt-4o",
#   messages=[{ "content": "Hello, how are you?",
#              "role": "user"}]
# )

# print(response.choices[0].message.content)