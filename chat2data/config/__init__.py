"""Configuration management for Chat2Data"""

from .settings import Config
from .central_config import CentralConfig, get_config, reset_config
from .central_config import (
    get_ollama_url,
    get_ollama_model,
    get_default_database_path,
    get_demo_database_path,
    get_vector_ollama_url,
    get_embedding_model
)

__all__ = [
    "Config",
    "CentralConfig",
    "get_config",
    "reset_config",
    "get_ollama_url",
    "get_ollama_model",
    "get_default_database_path",
    "get_demo_database_path",
    "get_vector_ollama_url",
    "get_embedding_model"
]