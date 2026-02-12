from dotenv import load_dotenv
import os

load_dotenv()
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL_SEARCH: str = os.environ.get("OPENAI_MODEL_SEARCH", "gpt-5")
OPENAI_MODEL_EXTRACT: str = os.environ.get("OPENAI_MODEL_EXTRACT", "gpt-5")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY environment variable is not set")