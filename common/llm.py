import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError(
        "GROQ_API_KEY environment variable is not set. "
        "Please set it in your Hugging Face Space settings under 'Variables and secrets'."
    )

groq_model = ChatGroq(
    model="moonshotai/kimi-k2-instruct-0905",
    api_key=GROQ_API_KEY,
    temperature=0.3
)



# openrouter_api_key = os.getenv("OPEN_ROUTER_API_KEY")
# gemini_model = ChatOpenAI(
#     model="google/gemini-2.0-flash-lite-001",
#     api_key=openrouter_api_key,
#     base_url="https://openrouter.ai/api/v1",
#     temperature=0.3,
# )