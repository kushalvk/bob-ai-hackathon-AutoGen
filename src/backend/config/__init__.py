"""Configuration settings for ClinGuard AI backend application."""

import os
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration settings loaded from environment variables or defaults.
    
    Attributes:
        PROJECT_NAME (str): Name of the application service.
        DATABASE_URL (str): Database connection string. Defaults to SQLite for local dev.
        DEBUG (bool): Debug mode flag.
        LLM_PROVIDER (str): LLM provider for severity classification.
            Set to 'watsonx' to enable LLM-based severity review. Empty = deterministic only.
        WATSONX_API_KEY (str): IBM Cloud API key for watsonx.ai.
        WATSONX_PROJECT_ID (str): watsonx.ai project identifier.
        WATSONX_URL (str): watsonx.ai endpoint URL.
        WATSONX_MODEL_ID (str): Foundation model ID for severity classification.
    """
    PROJECT_NAME: str = "ClinGuard AI Backend"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./clinguard.db")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

    # LLM Severity Classification settings
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "")
    WATSONX_API_KEY: str = os.getenv("WATSONX_API_KEY", "")
    WATSONX_PROJECT_ID: str = os.getenv("WATSONX_PROJECT_ID", "")
    WATSONX_URL: str = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
    WATSONX_MODEL_ID: str = os.getenv("WATSONX_MODEL_ID", "ibm/granite-13b-instruct-v2")

    model_config = ConfigDict(env_file=".env", extra="ignore")



CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
RISK_WEIGHTS_PATH = os.path.join(CONFIG_DIR, "risk_weights.json")

settings = Settings()

