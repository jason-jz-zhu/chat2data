"""Configuration management with auto-detection"""

import os
import logging
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from pathlib import Path

logger = logging.getLogger(__name__)


class LLMConfig(BaseModel):
    """LLM provider configuration"""
    provider: str = Field(default="ollama", description="LLM provider (mock, ollama)")
    model_name: str = Field(default="llama3.2:latest", description="Model name for LLM")
    base_url: str = Field(default="http://localhost:11434", description="Base URL for LLM service")
    api_key: Optional[str] = Field(default=None, description="API key if required")


class DatabaseConfig(BaseModel):
    """Database provider configuration"""
    provider: str = Field(default="sqlite", description="Database provider (sqlite)")
    path: str = Field(default="./data/chat2data.db", description="Database path")
    connection_string: Optional[str] = Field(default=None, description="Database connection string")


class VectorStoreConfig(BaseModel):
    """Vector store provider configuration"""
    provider: str = Field(default="memory", description="Vector store provider (memory, chromadb)")
    path: Optional[str] = Field(default=None, description="Vector store path")


class ServerConfig(BaseModel):
    """Server configuration"""
    host: str = Field(default="localhost", description="Server host")
    port: int = Field(default=5000, description="Server port")
    debug: bool = Field(default=False, description="Debug mode")


class Config(BaseModel):
    """Main configuration class with auto-detection"""
    llm: LLMConfig = Field(default_factory=LLMConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)

    @classmethod
    def from_env(cls) -> "Config":
        """Create configuration from environment variables"""
        config = cls()

        # LLM configuration
        if os.getenv("CHAT2DATA_LLM_PROVIDER"):
            config.llm.provider = os.getenv("CHAT2DATA_LLM_PROVIDER")
        if os.getenv("CHAT2DATA_LLM_MODEL"):
            config.llm.model_name = os.getenv("CHAT2DATA_LLM_MODEL")
        if os.getenv("CHAT2DATA_LLM_URL"):
            config.llm.base_url = os.getenv("CHAT2DATA_LLM_URL")
        if os.getenv("CHAT2DATA_LLM_API_KEY"):
            config.llm.api_key = os.getenv("CHAT2DATA_LLM_API_KEY")

        # Database configuration
        if os.getenv("CHAT2DATA_DB_PROVIDER"):
            config.database.provider = os.getenv("CHAT2DATA_DB_PROVIDER")
        if os.getenv("CHAT2DATA_DB_PATH"):
            config.database.path = os.getenv("CHAT2DATA_DB_PATH")
        if os.getenv("DATABASE_URL"):
            config.database.connection_string = os.getenv("DATABASE_URL")

        # Vector store configuration
        if os.getenv("CHAT2DATA_VECTOR_PROVIDER"):
            config.vector_store.provider = os.getenv("CHAT2DATA_VECTOR_PROVIDER")
        if os.getenv("CHAT2DATA_VECTOR_PATH"):
            config.vector_store.path = os.getenv("CHAT2DATA_VECTOR_PATH")

        # Server configuration
        if os.getenv("CHAT2DATA_HOST"):
            config.server.host = os.getenv("CHAT2DATA_HOST")
        if os.getenv("CHAT2DATA_PORT"):
            try:
                config.server.port = int(os.getenv("CHAT2DATA_PORT"))
            except ValueError:
                pass
        if os.getenv("CHAT2DATA_DEBUG"):
            config.server.debug = os.getenv("CHAT2DATA_DEBUG").lower() in ("true", "1", "yes")

        return config

    @classmethod
    def from_file(cls, config_path: str) -> "Config":
        """Load configuration from file"""
        config_file = Path(config_path)
        if not config_file.exists():
            logger.warning(f"Config file {config_path} not found, using defaults")
            return cls()

        try:
            if config_file.suffix.lower() == '.json':
                import json
                with open(config_file, 'r') as f:
                    data = json.load(f)
            elif config_file.suffix.lower() in ('.yml', '.yaml'):
                try:
                    import yaml
                    with open(config_file, 'r') as f:
                        data = yaml.safe_load(f)
                except ImportError:
                    logger.error("PyYAML not installed. Install with: pip install pyyaml")
                    return cls()
            else:
                logger.error(f"Unsupported config file format: {config_file.suffix}")
                return cls()

            return cls(**data)

        except Exception as e:
            logger.error(f"Error loading config from {config_path}: {e}")
            return cls()

    @classmethod
    def auto_detect(cls) -> "Config":
        """Auto-detect configuration from environment and files"""
        # Start with environment variables
        config = cls.from_env()

        # Check for config files in order of preference
        config_files = [
            "chat2data.json",
            "chat2data.yml",
            "chat2data.yaml",
            ".chat2data.json",
            ".chat2data.yml",
            ".chat2data.yaml",
            os.path.expanduser("~/.chat2data.json"),
            os.path.expanduser("~/.chat2data.yml"),
        ]

        for config_file in config_files:
            if os.path.exists(config_file):
                logger.info(f"Loading configuration from {config_file}")
                file_config = cls.from_file(config_file)
                # Merge with environment config (env takes precedence)
                config = cls._merge_configs(file_config, config)
                break

        # Auto-detect available providers
        config = cls._auto_detect_providers(config)

        return config

    @classmethod
    def _merge_configs(cls, base_config: "Config", override_config: "Config") -> "Config":
        """Merge two configurations with override taking precedence"""
        # This is a simple implementation - in a real scenario you might want more sophisticated merging
        merged_data = base_config.model_dump()
        override_data = override_config.model_dump()

        # Merge nested dictionaries
        for key, value in override_data.items():
            if isinstance(value, dict) and key in merged_data:
                for sub_key, sub_value in value.items():
                    if sub_value is not None:  # Only override if not None
                        merged_data[key][sub_key] = sub_value
            elif value is not None:
                merged_data[key] = value

        return cls(**merged_data)

    @classmethod
    def _auto_detect_providers(cls, config: "Config") -> "Config":
        """Auto-detect available providers and adjust configuration"""
        # Detect Ollama availability
        if config.llm.provider == "ollama":
            try:
                import requests
                response = requests.get(f"{config.llm.base_url}/api/tags", timeout=5)
                if response.status_code != 200:
                    logger.warning("Ollama not available at %s. Please ensure Ollama is running.", config.llm.base_url)
                    # Still keep ollama as default, just warn the user
            except Exception as e:
                logger.warning("Ollama not available at %s: %s. Please ensure Ollama is running.", config.llm.base_url, str(e))
                # Still keep ollama as default, just warn the user

        # Ensure database directory exists
        if config.database.provider == "sqlite":
            db_path = Path(config.database.path)
            db_path.parent.mkdir(parents=True, exist_ok=True)

        return config

    def save_to_file(self, config_path: str):
        """Save configuration to file"""
        config_file = Path(config_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            if config_file.suffix.lower() == '.json':
                import json
                with open(config_file, 'w') as f:
                    json.dump(self.model_dump(), f, indent=2)
            elif config_file.suffix.lower() in ('.yml', '.yaml'):
                try:
                    import yaml
                    with open(config_file, 'w') as f:
                        yaml.dump(self.model_dump(), f, default_flow_style=False)
                except ImportError:
                    logger.error("PyYAML not installed. Install with: pip install pyyaml")
                    return False
            else:
                logger.error(f"Unsupported config file format: {config_file.suffix}")
                return False

            logger.info(f"Configuration saved to {config_path}")
            return True

        except Exception as e:
            logger.error(f"Error saving config to {config_path}: {e}")
            return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return self.model_dump()