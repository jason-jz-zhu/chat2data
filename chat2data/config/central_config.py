"""Central configuration management for Chat2Data

This module provides a single source of truth for all configuration defaults
with environment variable support to eliminate hardcoded values throughout the codebase.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """LLM provider configuration"""
    provider: str = field(default_factory=lambda: os.getenv("CHAT2DATA_LLM_PROVIDER", "ollama"))
    model_name: str = field(default_factory=lambda: os.getenv("CHAT2DATA_LLM_MODEL", "llama3.2:latest"))
    base_url: str = field(default_factory=lambda: os.getenv("CHAT2DATA_LLM_URL", "http://localhost:11434"))
    api_key: Optional[str] = field(default_factory=lambda: os.getenv("CHAT2DATA_LLM_API_KEY"))

    # Specific model alternatives for different use cases
    sql_model: str = field(default_factory=lambda: os.getenv("CHAT2DATA_SQL_MODEL", "sqlcoder:latest"))
    embedding_model: str = field(default_factory=lambda: os.getenv("CHAT2DATA_EMBEDDING_MODEL", "llama3.2:latest"))


@dataclass
class DatabaseConfig:
    """Database configuration"""
    provider: str = field(default_factory=lambda: os.getenv("CHAT2DATA_DB_PROVIDER", "sqlite"))
    path: str = field(default_factory=lambda: os.getenv("CHAT2DATA_DB_PATH", "./data/chat2data.db"))
    demo_path: str = field(default_factory=lambda: os.getenv("CHAT2DATA_DEMO_DB_PATH", "./data/chat2data.db"))

    # Connection settings for other database types
    host: Optional[str] = field(default_factory=lambda: os.getenv("CHAT2DATA_DB_HOST"))
    port: Optional[int] = field(default_factory=lambda: int(os.getenv("CHAT2DATA_DB_PORT", "0")) or None)
    username: Optional[str] = field(default_factory=lambda: os.getenv("CHAT2DATA_DB_USERNAME"))
    password: Optional[str] = field(default_factory=lambda: os.getenv("CHAT2DATA_DB_PASSWORD"))
    database: Optional[str] = field(default_factory=lambda: os.getenv("CHAT2DATA_DB_NAME"))


@dataclass
class VectorStoreConfig:
    """Vector store configuration"""
    provider: str = field(default_factory=lambda: os.getenv("CHAT2DATA_VECTOR_PROVIDER", "semantic"))
    ollama_url: str = field(default_factory=lambda: os.getenv("CHAT2DATA_VECTOR_OLLAMA_URL", "http://localhost:11434"))
    embedding_model: str = field(default_factory=lambda: os.getenv("CHAT2DATA_VECTOR_EMBEDDING_MODEL", "llama2"))

    # Chroma/other vector store settings
    persist_directory: str = field(default_factory=lambda: os.getenv("CHAT2DATA_VECTOR_PERSIST_DIR", "./vector_store"))
    collection_name: str = field(default_factory=lambda: os.getenv("CHAT2DATA_VECTOR_COLLECTION", "chat2data"))


@dataclass
class UIConfig:
    """UI and frontend configuration"""
    default_provider: str = field(default_factory=lambda: os.getenv("CHAT2DATA_UI_DEFAULT_PROVIDER", "ollama"))
    default_database: str = field(default_factory=lambda: os.getenv("CHAT2DATA_UI_DEFAULT_DATABASE", "./data/chat2data.db"))
    streamlit_port: int = field(default_factory=lambda: int(os.getenv("CHAT2DATA_UI_PORT", "8501")))
    streamlit_host: str = field(default_factory=lambda: os.getenv("CHAT2DATA_UI_HOST", "localhost"))


@dataclass
class PathConfig:
    """Path configuration for various data directories"""
    data_dir: str = field(default_factory=lambda: os.getenv("CHAT2DATA_DATA_DIR", "./data"))
    cache_dir: str = field(default_factory=lambda: os.getenv("CHAT2DATA_CACHE_DIR", "./cache"))
    logs_dir: str = field(default_factory=lambda: os.getenv("CHAT2DATA_LOGS_DIR", "./logs"))
    config_dir: str = field(default_factory=lambda: os.getenv("CHAT2DATA_CONFIG_DIR", "."))


@dataclass
class AdaptiveConfig:
    """Configuration for adaptive/dynamic features"""
    enable_domain_adaptation: bool = field(default_factory=lambda: os.getenv("CHAT2DATA_ENABLE_ADAPTATION", "true").lower() == "true")
    schema_cache_ttl: int = field(default_factory=lambda: int(os.getenv("CHAT2DATA_SCHEMA_CACHE_TTL", "3600")))
    max_examples_per_domain: int = field(default_factory=lambda: int(os.getenv("CHAT2DATA_MAX_EXAMPLES", "10")))
    enable_schema_discovery: bool = field(default_factory=lambda: os.getenv("CHAT2DATA_ENABLE_SCHEMA_DISCOVERY", "true").lower() == "true")


class CentralConfig:
    """Central configuration manager for Chat2Data"""

    def __init__(self):
        self.llm = LLMConfig()
        self.database = DatabaseConfig()
        self.vector_store = VectorStoreConfig()
        self.ui = UIConfig()
        self.paths = PathConfig()
        self.adaptive = AdaptiveConfig()

        # Ensure data directories exist
        self._ensure_directories()

        logger.info("Central configuration initialized")
        self._log_config_summary()

    def _ensure_directories(self):
        """Ensure all configured directories exist"""
        directories = [
            self.paths.data_dir,
            self.paths.cache_dir,
            self.paths.logs_dir,
            os.path.dirname(self.database.path),
            os.path.dirname(self.database.demo_path),
            self.vector_store.persist_directory
        ]

        for directory in directories:
            if directory and directory != ".":
                Path(directory).mkdir(parents=True, exist_ok=True)

    def _log_config_summary(self):
        """Log configuration summary for debugging"""
        logger.debug(f"LLM: {self.llm.provider} ({self.llm.model_name}) @ {self.llm.base_url}")
        logger.debug(f"Database: {self.database.provider} @ {self.database.path}")
        logger.debug(f"Vector Store: {self.vector_store.provider} @ {self.vector_store.ollama_url}")
        logger.debug(f"UI: Default provider={self.ui.default_provider}, port={self.ui.streamlit_port}")

    def get_database_path(self, use_demo: bool = False) -> str:
        """Get appropriate database path"""
        return self.database.demo_path if use_demo else self.database.path

    def get_ollama_config(self) -> Dict[str, Any]:
        """Get Ollama-specific configuration"""
        return {
            "base_url": self.llm.base_url,
            "model_name": self.llm.model_name,
            "sql_model": self.llm.sql_model,
            "embedding_model": self.llm.embedding_model
        }

    def get_vector_config(self) -> Dict[str, Any]:
        """Get vector store configuration"""
        return {
            "ollama_base_url": self.vector_store.ollama_url,
            "embedding_model": self.vector_store.embedding_model,
            "persist_directory": self.vector_store.persist_directory,
            "collection_name": self.vector_store.collection_name
        }

    def get_ui_defaults(self) -> Dict[str, Any]:
        """Get UI default values"""
        return {
            "provider_type": self.ui.default_provider,
            "database_path": self.ui.default_database,
            "ollama_url": self.llm.base_url,
            "ollama_model": self.llm.model_name
        }

    def update_from_dict(self, config_dict: Dict[str, Any]):
        """Update configuration from dictionary (for config files)"""
        if "llm" in config_dict:
            llm_config = config_dict["llm"]
            if "provider" in llm_config:
                self.llm.provider = llm_config["provider"]
            if "model_name" in llm_config:
                self.llm.model_name = llm_config["model_name"]
            if "base_url" in llm_config:
                self.llm.base_url = llm_config["base_url"]

        if "database" in config_dict:
            db_config = config_dict["database"]
            if "provider" in db_config:
                self.database.provider = db_config["provider"]
            if "path" in db_config:
                self.database.path = db_config["path"]

        logger.info("Configuration updated from dictionary")

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for serialization"""
        return {
            "llm": {
                "provider": self.llm.provider,
                "model_name": self.llm.model_name,
                "base_url": self.llm.base_url,
                "sql_model": self.llm.sql_model,
                "embedding_model": self.llm.embedding_model
            },
            "database": {
                "provider": self.database.provider,
                "path": self.database.path,
                "demo_path": self.database.demo_path
            },
            "vector_store": {
                "provider": self.vector_store.provider,
                "ollama_url": self.vector_store.ollama_url,
                "embedding_model": self.vector_store.embedding_model,
                "persist_directory": self.vector_store.persist_directory
            },
            "ui": {
                "default_provider": self.ui.default_provider,
                "default_database": self.ui.default_database,
                "streamlit_port": self.ui.streamlit_port,
                "streamlit_host": self.ui.streamlit_host
            },
            "paths": {
                "data_dir": self.paths.data_dir,
                "cache_dir": self.paths.cache_dir,
                "logs_dir": self.paths.logs_dir,
                "config_dir": self.paths.config_dir
            },
            "adaptive": {
                "enable_domain_adaptation": self.adaptive.enable_domain_adaptation,
                "schema_cache_ttl": self.adaptive.schema_cache_ttl,
                "max_examples_per_domain": self.adaptive.max_examples_per_domain,
                "enable_schema_discovery": self.adaptive.enable_schema_discovery
            }
        }


# Global configuration instance
_config_instance: Optional[CentralConfig] = None


def get_config() -> CentralConfig:
    """Get the global configuration instance"""
    global _config_instance
    if _config_instance is None:
        _config_instance = CentralConfig()
    return _config_instance


def reset_config():
    """Reset the global configuration instance (mainly for testing)"""
    global _config_instance
    _config_instance = None


# Convenience functions for common configuration access
def get_ollama_url() -> str:
    """Get the configured Ollama URL"""
    return get_config().llm.base_url


def get_ollama_model() -> str:
    """Get the configured Ollama model"""
    return get_config().llm.model_name


def get_default_database_path() -> str:
    """Get the default database path"""
    return get_config().database.path


def get_demo_database_path() -> str:
    """Get the demo database path"""
    return get_config().database.demo_path


def get_vector_ollama_url() -> str:
    """Get the Ollama URL for vector operations"""
    return get_config().vector_store.ollama_url


def get_embedding_model() -> str:
    """Get the configured embedding model"""
    return get_config().llm.embedding_model