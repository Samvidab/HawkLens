
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(
    vertexai=True,
    api_key=os.environ["VERTEX_API_KEY"]
)

response = client.models.generate_content(
    model="gemini-3.5-flash-lite",
    contents="Say hello in one sentence."
)

print(response.text)
