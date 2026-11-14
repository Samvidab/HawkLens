
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

print("Starting test...", flush=True)

# Step 1: Create Vertex AI client
client = genai.Client(
    vertexai=True,
    api_key=os.environ["VERTEX_API_KEY"],
    http_options=types.HttpOptions(api_version="v1")
)

# Step 2: Test direct Google SDK
print("Testing direct Vertex SDK...", flush=True)

response = client.models.generate_content(
    model="gemini-3.5-flash-lite",
    contents="Say hello"
)

print("Direct SDK:", response.text, flush=True)

# Step 3: Create LangChain model
print("Creating LangChain model...", flush=True)

model = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    vertexai=True,
    google_api_key=os.environ["VERTEX_API_KEY"]
)

# Step 4: Replace LangChain's client with our working Vertex client
model.client = client

# Step 5: Verify the client
print("Same client:", model.client is client, flush=True)
print(
    "API version:",
    model.client._api_client._http_options.api_version,
    flush=True
)

# Step 6: Test LangChain
print("Testing LangChain...", flush=True)

response = model.invoke("Say hello")

print("LangChain:", response.content, flush=True)

print("All tests passed!", flush=True)
