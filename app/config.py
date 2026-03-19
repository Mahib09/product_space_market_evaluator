from dotenv import load_dotenv
import os

load_dotenv(override=False)  # never overwrite an already-set env var

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL_SEARCH: str = os.environ.get("OPENAI_MODEL_SEARCH", "gpt-4.1")
OPENAI_MODEL_EXTRACT: str = os.environ.get("OPENAI_MODEL_EXTRACT", "gpt-5")

AGENT1_TIMEOUT: int = int(os.environ.get("AGENT1_TIMEOUT", "1000"))
AGENT2_TIMEOUT: int = int(os.environ.get("AGENT2_TIMEOUT", "1000"))
AGENT3_TIMEOUT: int = int(os.environ.get("AGENT3_TIMEOUT", "1250"))