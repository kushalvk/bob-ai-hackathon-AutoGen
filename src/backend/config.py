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
    """
    PROJECT_NAME: str = "ClinGuard AI Backend"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./clinguard.db")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

    model_config = ConfigDict(env_file=".env", extra="ignore")


settings = Settings()
