"""
Amar Tax AI Agent - Configuration & LLM Initialization
Configures LLMs with seamless multi-provider support:
Google Gemini (gemini/gemini-3.5-flash-lite), Groq, or OpenAI.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger("AmarTax.Config")

# Load environment variables
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

# Sanitize litellm messages to prevent provider compatibility issues
try:
    import litellm
    litellm.drop_params = True

    _orig_completion = litellm.completion
    def _sanitized_completion(*args, **kwargs):
        if "messages" in kwargs and isinstance(kwargs["messages"], list):
            for msg in kwargs["messages"]:
                if isinstance(msg, dict):
                    msg.pop("cache_breakpoint", None)
        return _orig_completion(*args, **kwargs)

    litellm.completion = _sanitized_completion
except ImportError:
    pass


def get_llm(model_name: str = None):
    """
    Initializes and returns a CrewAI LLM instance.
    Checks environment for custom model overrides, or auto-detects from available keys:
      1. Explicit `MODEL_NAME` env var
      2. GEMINI_API_KEY -> gemini/gemini-3.5-flash-lite
      3. GROQ_API_KEY   -> groq/openai/gpt-oss-120b
      4. OPENAI_API_KEY -> gpt-4o-mini
    """
    from crewai import LLM

    chosen_model = model_name or os.environ.get("MODEL_NAME") or os.environ.get("LLM_MODEL")

    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    groq_key = os.environ.get("GROQ_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if chosen_model:
        logger.info(f"Using explicitly specified LLM model: {chosen_model}")
        return LLM(model=chosen_model, temperature=0.1)

    if gemini_key:
        target_model = "gemini/gemini-3.5-flash-lite"
        logger.info(f"Initializing CrewAI with Google Gemini ({target_model})...")
        os.environ["GEMINI_API_KEY"] = gemini_key
        return LLM(
            model=target_model,
            api_key=gemini_key,
            temperature=0.1
        )
    elif groq_key:
        target_model = "groq/openai/gpt-oss-120b"
        logger.info(f"Initializing CrewAI with Groq ({target_model})...")
        return LLM(
            model=target_model,
            api_key=groq_key,
            temperature=0.1
        )
    elif openai_key:
        logger.info("Initializing CrewAI with OpenAI (gpt-4o-mini)...")
        return LLM(
            model="gpt-4o-mini",
            api_key=openai_key,
            temperature=0.1
        )
    else:
        logger.warning(
            "No API key detected in environment. Please configure .env file."
        )
        return LLM(
            model="gemini/gemini-3.5-flash-lite",
            temperature=0.1
        )
