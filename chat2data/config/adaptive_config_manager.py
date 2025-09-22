"""Adaptive Configuration Manager for Chat2Data Framework

Handles automatic configuration creation, persistence, and easy adoption
for any database schema while preserving accuracy mechanisms.
"""

import logging
import json
import os
import shutil
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
import hashlib

from ..core.schema_discovery import SchemaAnalysis
from ..core.dynamic_template_generator import DynamicQueryTemplates
from ..core.domain_adapter import DomainConfiguration

logger = logging.getLogger(__name__)


@dataclass
class AdaptiveConfig:
    """Complete adaptive configuration for Chat2Data"""
    # Basic information
    config_name: str
    version: str
    created_at: str
    last_updated: str

    # Database configuration
    database_config: Dict[str, Any]

    # LLM configuration
    llm_config: Dict[str, Any]

    # Vector store configuration
    vector_config: Dict[str, Any]

    # Domain adaptation configuration
    domain_config: Dict[str, Any]

    # Accuracy settings
    accuracy_config: Dict[str, Any]

    # Schema fingerprint for change detection
    schema_fingerprint: str

    # Environment settings
    environment: str = "production"


@dataclass
class ConfigTemplate:
    """Configuration template for different domains"""
    template_name: str
    domain_type: str
    description: str
    default_settings: Dict[str, Any]
    required_tables: List[str]
    optional_features: List[str]


class AdaptiveConfigManager:
    """Manages adaptive configurations for Chat2Data"""

    def __init__(self, config_dir: str = None):
        """Initialize the adaptive config manager"""
        self.config_dir = Path(config_dir or os.path.expanduser("~/.chat2data"))
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Configuration files
        self.configs_dir = self.config_dir / "configs"
        self.templates_dir = self.config_dir / "templates"
        self.backups_dir = self.config_dir / "backups"

        # Create directories
        for dir_path in [self.configs_dir, self.templates_dir, self.backups_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        # Built-in templates
        self.builtin_templates = self._load_builtin_templates()

        # Active configuration
        self.active_config: Optional[AdaptiveConfig] = None

    def create_adaptive_config(self,
                             database_path: str,
                             config_name: str = None,
                             domain_config: DomainConfiguration = None,
                             llm_settings: Dict[str, Any] = None,
                             environment: str = "production") -> AdaptiveConfig:
        """Create adaptive configuration from database analysis"""
        try:
            logger.info(f"Creating adaptive configuration for: {database_path}")

            # Generate config name if not provided
            if not config_name:
                config_name = self._generate_config_name(database_path)

            # Get database fingerprint
            schema_fingerprint = self._calculate_schema_fingerprint(database_path)

            # Create timestamp
            timestamp = datetime.now().isoformat()

            # Build database configuration
            database_config = {
                "provider": "sqlite",
                "path": database_path,
                "connection_params": {},
                "auto_schema_detection": True,
                "schema_cache_ttl": 3600  # 1 hour
            }

            # Build LLM configuration
            llm_config = {
                "provider": "ollama",
                "model_name": "llama3.2:latest",
                "base_url": "http://localhost:11434",
                "use_enhanced_provider": True,
                "system_prompt_template": "adaptive",
                "max_tokens": 2048,
                "temperature": 0.1,
                **(llm_settings or {})
            }

            # Build vector store configuration
            vector_config = {
                "provider": "semantic",
                "embedding_model": llm_config["model_name"],
                "ollama_base_url": llm_config["base_url"],
                "chunk_size": 512,
                "overlap": 50,
                "similarity_threshold": 0.7,
                "max_results": 10
            }

            # Build domain configuration
            domain_adaptation = {}
            if domain_config:
                domain_adaptation = {
                    "schema_name": domain_config.schema_name,
                    "confidence_threshold": domain_config.confidence_threshold,
                    "use_smart_pipeline": domain_config.use_smart_pipeline,
                    "template_cache_enabled": True,
                    "auto_update_templates": True,
                    "fallback_to_static": True
                }

            # Build accuracy configuration
            accuracy_config = {
                "confidence_threshold": 0.7,
                "use_few_shot_examples": True,
                "max_few_shot_examples": 10,
                "use_schema_context": True,
                "use_relationship_hints": True,
                "enable_query_validation": True,
                "enable_result_summarization": True,
                "learning_enabled": True,
                "feedback_collection": True
            }

            # Create adaptive config
            adaptive_config = AdaptiveConfig(
                config_name=config_name,
                version="1.0.0",
                created_at=timestamp,
                last_updated=timestamp,
                database_config=database_config,
                llm_config=llm_config,
                vector_config=vector_config,
                domain_config=domain_adaptation,
                accuracy_config=accuracy_config,
                schema_fingerprint=schema_fingerprint,
                environment=environment
            )

            # Save configuration
            self._save_config(adaptive_config)

            # Set as active configuration
            self.active_config = adaptive_config

            logger.info(f"Created adaptive configuration: {config_name}")
            return adaptive_config

        except Exception as e:
            logger.error(f"Error creating adaptive configuration: {e}")
            raise

    def load_config(self, config_name: str) -> AdaptiveConfig:
        """Load configuration by name"""
        config_file = self.configs_dir / f"{config_name}.json"

        if not config_file.exists():
            raise FileNotFoundError(f"Configuration not found: {config_name}")

        try:
            with open(config_file, 'r') as f:
                config_data = json.load(f)

            adaptive_config = AdaptiveConfig(**config_data)
            self.active_config = adaptive_config

            logger.info(f"Loaded configuration: {config_name}")
            return adaptive_config

        except Exception as e:
            logger.error(f"Error loading configuration {config_name}: {e}")
            raise

    def save_config(self, config: AdaptiveConfig) -> None:
        """Save configuration to disk"""
        try:
            config.last_updated = datetime.now().isoformat()
            self._save_config(config)
            logger.info(f"Saved configuration: {config.config_name}")

        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            raise

    def _save_config(self, config: AdaptiveConfig) -> None:
        """Internal method to save configuration"""
        config_file = self.configs_dir / f"{config.config_name}.json"

        # Create backup if config exists
        if config_file.exists():
            self._create_backup(config.config_name)

        # Save configuration
        with open(config_file, 'w') as f:
            json.dump(asdict(config), f, indent=2)

    def update_schema_analysis(self,
                             config_name: str,
                             domain_config: DomainConfiguration) -> AdaptiveConfig:
        """Update configuration with new schema analysis"""
        try:
            # Load existing configuration
            config = self.load_config(config_name)

            # Update schema fingerprint
            new_fingerprint = self._calculate_schema_fingerprint(
                config.database_config["path"]
            )

            # Check if schema has changed
            schema_changed = new_fingerprint != config.schema_fingerprint

            if schema_changed:
                logger.info("Schema change detected, updating configuration...")

                # Update domain configuration
                config.domain_config.update({
                    "schema_name": domain_config.schema_name,
                    "confidence_threshold": domain_config.confidence_threshold,
                    "use_smart_pipeline": domain_config.use_smart_pipeline,
                    "last_schema_update": datetime.now().isoformat()
                })

                # Update schema fingerprint
                config.schema_fingerprint = new_fingerprint

                # Increment version
                config.version = self._increment_version(config.version)

                # Save updated configuration
                self.save_config(config)

                logger.info(f"Updated configuration for schema changes: {config_name}")
            else:
                logger.info("No schema changes detected")

            return config

        except Exception as e:
            logger.error(f"Error updating schema analysis: {e}")
            raise

    def create_from_template(self,
                           template_name: str,
                           database_path: str,
                           config_name: str = None,
                           custom_settings: Dict[str, Any] = None) -> AdaptiveConfig:
        """Create configuration from template"""
        try:
            # Get template
            template = self._get_template(template_name)

            if not template:
                raise ValueError(f"Template not found: {template_name}")

            # Generate config name
            if not config_name:
                config_name = f"{template.template_name}_{self._generate_timestamp()}"

            # Merge template settings with custom settings
            settings = template.default_settings.copy()
            if custom_settings:
                settings.update(custom_settings)

            # Create configuration using template
            config = self.create_adaptive_config(
                database_path=database_path,
                config_name=config_name,
                llm_settings=settings.get("llm", {}),
                environment=settings.get("environment", "production")
            )

            # Apply template-specific settings
            if "accuracy" in settings:
                config.accuracy_config.update(settings["accuracy"])

            if "vector" in settings:
                config.vector_config.update(settings["vector"])

            # Save updated configuration
            self.save_config(config)

            logger.info(f"Created configuration from template {template_name}: {config_name}")
            return config

        except Exception as e:
            logger.error(f"Error creating configuration from template: {e}")
            raise

    def list_configurations(self) -> List[Dict[str, Any]]:
        """List all available configurations"""
        configs = []

        for config_file in self.configs_dir.glob("*.json"):
            try:
                with open(config_file, 'r') as f:
                    config_data = json.load(f)

                config_info = {
                    "name": config_data.get("config_name"),
                    "version": config_data.get("version"),
                    "created_at": config_data.get("created_at"),
                    "last_updated": config_data.get("last_updated"),
                    "environment": config_data.get("environment"),
                    "database_path": config_data.get("database_config", {}).get("path"),
                    "schema_name": config_data.get("domain_config", {}).get("schema_name")
                }
                configs.append(config_info)

            except Exception as e:
                logger.warning(f"Error reading config file {config_file}: {e}")

        return sorted(configs, key=lambda x: x.get("last_updated", ""), reverse=True)

    def delete_configuration(self, config_name: str) -> None:
        """Delete configuration"""
        config_file = self.configs_dir / f"{config_name}.json"

        if not config_file.exists():
            raise FileNotFoundError(f"Configuration not found: {config_name}")

        # Create backup before deletion
        self._create_backup(config_name)

        # Delete configuration file
        config_file.unlink()

        # Clear active config if it's the one being deleted
        if self.active_config and self.active_config.config_name == config_name:
            self.active_config = None

        logger.info(f"Deleted configuration: {config_name}")

    def validate_configuration(self, config: AdaptiveConfig) -> Tuple[bool, List[str]]:
        """Validate configuration completeness and correctness"""
        errors = []

        # Validate database configuration
        if not config.database_config.get("path"):
            errors.append("Database path is required")

        db_path = config.database_config.get("path")
        if db_path and not os.path.exists(db_path) and db_path != ":memory:":
            errors.append(f"Database file not found: {db_path}")

        # Validate LLM configuration
        if not config.llm_config.get("provider"):
            errors.append("LLM provider is required")

        if not config.llm_config.get("model_name"):
            errors.append("LLM model name is required")

        # Validate accuracy configuration
        confidence = config.accuracy_config.get("confidence_threshold")
        if confidence is not None and (confidence < 0 or confidence > 1):
            errors.append("Confidence threshold must be between 0 and 1")

        # Validate schema fingerprint
        if config.schema_fingerprint:
            current_fingerprint = self._calculate_schema_fingerprint(db_path)
            if current_fingerprint != config.schema_fingerprint:
                errors.append("Schema has changed since configuration was created")

        return len(errors) == 0, errors

    def get_setup_recommendations(self, database_path: str) -> Dict[str, Any]:
        """Get setup recommendations for a database"""
        try:
            # Check if database exists
            if not os.path.exists(database_path):
                return {
                    "status": "error",
                    "message": f"Database file not found: {database_path}",
                    "recommendations": []
                }

            # Analyze database quickly
            from ..providers.database.sqlite_provider import SQLiteDatabaseProvider
            db_provider = SQLiteDatabaseProvider(database_path)

            try:
                schema_info = db_provider.get_schema()
                table_count = len(schema_info)

                recommendations = []

                # Template recommendations
                if table_count >= 3:
                    # Check for e-commerce patterns
                    table_names = [table.name.lower() for table in schema_info]
                    if any(name in table_names for name in ['products', 'orders', 'customers']):
                        recommendations.append({
                            "type": "template",
                            "template": "ecommerce",
                            "confidence": 0.9,
                            "reason": "Detected e-commerce table patterns"
                        })

                    # Check for CRM patterns
                    if any(name in table_names for name in ['contacts', 'leads', 'accounts']):
                        recommendations.append({
                            "type": "template",
                            "template": "crm",
                            "confidence": 0.8,
                            "reason": "Detected CRM table patterns"
                        })

                # Performance recommendations
                if table_count > 10:
                    recommendations.append({
                        "type": "performance",
                        "setting": "enable_schema_cache",
                        "value": True,
                        "reason": "Large schema detected, caching recommended"
                    })

                # Model recommendations
                recommendations.append({
                    "type": "model",
                    "model": "llama3.2:latest",
                    "confidence": 0.8,
                    "reason": "Good balance of accuracy and speed for SQL generation"
                })

                return {
                    "status": "success",
                    "table_count": table_count,
                    "recommendations": recommendations,
                    "estimated_setup_time": "2-5 minutes"
                }

            except Exception as e:
                return {
                    "status": "warning",
                    "message": f"Could not analyze database: {e}",
                    "recommendations": [
                        {
                            "type": "fallback",
                            "template": "general",
                            "reason": "Use general template as fallback"
                        }
                    ]
                }

        except Exception as e:
            logger.error(f"Error getting setup recommendations: {e}")
            return {
                "status": "error",
                "message": str(e),
                "recommendations": []
            }

    def export_configuration(self, config_name: str, export_path: str) -> None:
        """Export configuration for sharing"""
        config = self.load_config(config_name)

        # Create export package
        export_data = {
            "chat2data_config_export": True,
            "export_version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "configuration": asdict(config)
        }

        # Save export file
        with open(export_path, 'w') as f:
            json.dump(export_data, f, indent=2)

        logger.info(f"Exported configuration {config_name} to {export_path}")

    def import_configuration(self, import_path: str, new_config_name: str = None) -> AdaptiveConfig:
        """Import configuration from export file"""
        try:
            with open(import_path, 'r') as f:
                export_data = json.load(f)

            # Validate export format
            if not export_data.get("chat2data_config_export"):
                raise ValueError("Invalid export file format")

            # Extract configuration
            config_data = export_data["configuration"]

            # Update config name if provided
            if new_config_name:
                config_data["config_name"] = new_config_name

            # Update timestamps
            config_data["last_updated"] = datetime.now().isoformat()

            # Create configuration object
            config = AdaptiveConfig(**config_data)

            # Save imported configuration
            self._save_config(config)

            logger.info(f"Imported configuration: {config.config_name}")
            return config

        except Exception as e:
            logger.error(f"Error importing configuration: {e}")
            raise

    def _calculate_schema_fingerprint(self, database_path: str) -> str:
        """Calculate fingerprint of database schema for change detection"""
        try:
            from ..providers.database.sqlite_provider import SQLiteDatabaseProvider
            db_provider = SQLiteDatabaseProvider(database_path)
            schema_info = db_provider.get_schema()

            # Create schema signature
            schema_signature = []
            for table in schema_info:
                table_sig = f"{table.name}:{len(table.columns)}"
                schema_signature.append(table_sig)

            # Create hash
            signature_str = "|".join(sorted(schema_signature))
            return hashlib.md5(signature_str.encode()).hexdigest()

        except Exception as e:
            logger.warning(f"Could not calculate schema fingerprint: {e}")
            return "unknown"

    def _generate_config_name(self, database_path: str) -> str:
        """Generate configuration name from database path"""
        db_name = Path(database_path).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        return f"{db_name}_{timestamp}"

    def _generate_timestamp(self) -> str:
        """Generate timestamp for naming"""
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def _increment_version(self, version: str) -> str:
        """Increment version number"""
        try:
            parts = version.split('.')
            patch = int(parts[2]) + 1
            return f"{parts[0]}.{parts[1]}.{patch}"
        except:
            return "1.0.1"

    def _create_backup(self, config_name: str) -> None:
        """Create backup of configuration"""
        try:
            config_file = self.configs_dir / f"{config_name}.json"
            if config_file.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = self.backups_dir / f"{config_name}_{timestamp}.json"
                shutil.copy2(config_file, backup_file)

                # Keep only last 5 backups
                backups = list(self.backups_dir.glob(f"{config_name}_*.json"))
                if len(backups) > 5:
                    backups.sort(key=lambda x: x.stat().st_mtime)
                    for old_backup in backups[:-5]:
                        old_backup.unlink()

        except Exception as e:
            logger.warning(f"Could not create backup: {e}")

    def _load_builtin_templates(self) -> List[ConfigTemplate]:
        """Load built-in configuration templates"""
        return [
            ConfigTemplate(
                template_name="ecommerce",
                domain_type="E-commerce",
                description="Optimized for product catalogs, orders, and customers",
                default_settings={
                    "accuracy": {
                        "confidence_threshold": 0.8,
                        "max_few_shot_examples": 15
                    },
                    "llm": {
                        "temperature": 0.1,
                        "max_tokens": 2048
                    }
                },
                required_tables=["products", "orders", "customers"],
                optional_features=["categories", "order_items", "payments"]
            ),
            ConfigTemplate(
                template_name="crm",
                domain_type="Customer Relationship Management",
                description="Optimized for contacts, leads, and sales data",
                default_settings={
                    "accuracy": {
                        "confidence_threshold": 0.75,
                        "max_few_shot_examples": 12
                    }
                },
                required_tables=["contacts", "leads"],
                optional_features=["accounts", "opportunities", "campaigns"]
            ),
            ConfigTemplate(
                template_name="general",
                domain_type="General Purpose",
                description="Balanced settings for general databases",
                default_settings={
                    "accuracy": {
                        "confidence_threshold": 0.7,
                        "max_few_shot_examples": 10
                    }
                },
                required_tables=[],
                optional_features=[]
            )
        ]

    def _get_template(self, template_name: str) -> Optional[ConfigTemplate]:
        """Get template by name"""
        for template in self.builtin_templates:
            if template.template_name == template_name:
                return template
        return None

    def get_active_config(self) -> Optional[AdaptiveConfig]:
        """Get currently active configuration"""
        return self.active_config

    def set_active_config(self, config_name: str) -> AdaptiveConfig:
        """Set active configuration"""
        config = self.load_config(config_name)
        self.active_config = config
        return config