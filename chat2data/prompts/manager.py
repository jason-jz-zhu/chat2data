"""Central Prompt Manager for Chat2Data System"""
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
import yaml
import json
from string import Template

from .registry import PromptRegistry

logger = logging.getLogger(__name__)


class PromptManager:
    """
    Central manager for all prompt operations in Chat2Data.
    Handles static prompts, dynamic generation, and template substitution.
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize the PromptManager with configuration.

        Args:
            config_path: Path to the prompt configuration file
        """
        self.config_path = config_path or Path(__file__).parent / "config" / "prompts.yaml"
        self.registry = PromptRegistry()
        self._cache = {}
        self._load_configuration()

    def _load_configuration(self):
        """Load prompt configuration from YAML files"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config = yaml.safe_load(f)
                    self._load_prompts_from_config(config)

            # Load template files
            templates_dir = Path(__file__).parent / "templates"
            if templates_dir.exists():
                for template_file in templates_dir.glob("*.yaml"):
                    self._load_template_file(template_file)
        except Exception as e:
            logger.error(f"Error loading prompt configuration: {e}")

    def _load_prompts_from_config(self, config: Dict[str, Any]):
        """Load prompts from configuration dictionary"""
        if 'prompts' in config:
            for category, prompts in config['prompts'].items():
                for name, prompt_data in prompts.items():
                    self.registry.register(
                        name=f"{category}.{name}",
                        prompt=prompt_data
                    )

    def _load_template_file(self, file_path: Path):
        """Load a single template file"""
        try:
            with open(file_path, 'r') as f:
                templates = yaml.safe_load(f)
                category = file_path.stem  # Use filename as category
                if templates:
                    for name, template in templates.items():
                        self.registry.register(
                            name=f"{category}.{name}",
                            prompt=template
                        )
        except Exception as e:
            logger.error(f"Error loading template file {file_path}: {e}")

    def get_prompt(self,
                   prompt_type: str,
                   provider: Optional[str] = None,
                   context: Optional[Dict[str, Any]] = None) -> str:
        """
        Get a prompt with optional provider-specific overrides and context substitution.

        Args:
            prompt_type: Type of prompt (e.g., 'sql_generation', 'summary_generation')
            provider: Optional provider name for specific overrides
            context: Optional context for template variable substitution

        Returns:
            The formatted prompt string
        """
        cache_key = f"{prompt_type}:{provider}:{json.dumps(sorted(context.items()) if context else {})}"

        # Check cache
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Get base prompt
        prompt = self._get_base_prompt(prompt_type, provider)

        # Apply context substitution
        if context:
            prompt = self._substitute_variables(prompt, context)

        # Cache result
        self._cache[cache_key] = prompt

        return prompt

    def _get_base_prompt(self, prompt_type: str, provider: Optional[str] = None) -> str:
        """Get base prompt with provider-specific overrides"""
        # Try provider-specific first
        if provider:
            provider_key = f"{prompt_type}.{provider}"
            if self.registry.has(provider_key):
                return self.registry.get(provider_key)

        # Fall back to general prompt
        if self.registry.has(prompt_type):
            return self.registry.get(prompt_type)

        # Return default if nothing found
        logger.warning(f"No prompt found for type: {prompt_type}")
        return self._get_default_prompt(prompt_type)

    def _substitute_variables(self, prompt: str, context: Dict[str, Any]) -> str:
        """Substitute template variables in the prompt"""
        try:
            # Handle nested dictionaries and lists
            flat_context = self._flatten_context(context)

            # Use safe substitution to avoid KeyError
            template = Template(prompt)
            return template.safe_substitute(**flat_context)
        except Exception as e:
            logger.error(f"Error substituting variables: {e}")
            return prompt

    def _flatten_context(self, context: Dict[str, Any], prefix: str = '') -> Dict[str, str]:
        """Flatten nested context for template substitution"""
        flat = {}
        for key, value in context.items():
            full_key = f"{prefix}{key}" if prefix else key

            if isinstance(value, dict):
                flat.update(self._flatten_context(value, f"{full_key}_"))
            elif isinstance(value, list):
                flat[full_key] = ', '.join(str(v) for v in value)
            else:
                flat[full_key] = str(value)

        return flat

    def _get_default_prompt(self, prompt_type: str) -> str:
        """Get default prompts for common types"""
        defaults = {
            'sql_generation': """You are an expert SQL query generator.
Generate only SELECT queries based on the provided schema and question.
Return only the SQL query without explanation.""",

            'summary_generation': """Summarize the query results in natural language.
Be concise and accurate about the data counts.""",

            'error_correction': """Fix the SQL query error and return a corrected version."""
        }

        return defaults.get(prompt_type, "Process the request based on the context provided.")

    def register_prompt(self, name: str, prompt: str, override: bool = False):
        """
        Register a new prompt or update existing one.

        Args:
            name: Prompt identifier
            prompt: Prompt template string
            override: Whether to override existing prompt
        """
        if self.registry.has(name) and not override:
            logger.warning(f"Prompt {name} already exists. Use override=True to replace.")
            return

        self.registry.register(name, prompt)
        # Clear cache when new prompt is registered
        self._clear_cache()

    def update_prompt(self, name: str, prompt: str):
        """Update an existing prompt"""
        self.register_prompt(name, prompt, override=True)

    def get_dynamic_prompt(self,
                          prompt_type: str,
                          schema_analysis: Any,
                          provider: Optional[str] = None) -> str:
        """
        Generate a dynamic prompt based on schema analysis.

        Args:
            prompt_type: Type of prompt
            schema_analysis: Database schema analysis object
            provider: Optional provider name

        Returns:
            Dynamically generated prompt
        """
        # Start with base prompt
        base_prompt = self.get_prompt(prompt_type, provider)

        # Add schema-specific enhancements
        if schema_analysis:
            schema_context = self._generate_schema_context(schema_analysis)
            return f"{base_prompt}\n\n{schema_context}"

        return base_prompt

    def _generate_schema_context(self, schema_analysis: Any) -> str:
        """Generate context from schema analysis"""
        context_parts = ["## Database Schema Context:"]

        # Add table information
        if hasattr(schema_analysis, 'tables'):
            context_parts.append("\n### Tables:")
            for table in schema_analysis.tables[:10]:  # Limit to 10 tables
                context_parts.append(f"- {table.name}: {table.table_type}")

        # Add relationships
        if hasattr(schema_analysis, 'relationships'):
            context_parts.append("\n### Key Relationships:")
            for rel in schema_analysis.relationships[:5]:  # Limit to 5 relationships
                if rel.get('confidence', 0) > 0.7:
                    context_parts.append(
                        f"- {rel['from_table']}.{rel['from_column']} → "
                        f"{rel['to_table']}.{rel['to_column']}"
                    )

        return '\n'.join(context_parts)

    def list_prompts(self) -> List[str]:
        """List all registered prompt names"""
        return self.registry.list_all()

    def get_prompt_metadata(self, name: str) -> Optional[Dict[str, Any]]:
        """Get metadata about a specific prompt"""
        if self.registry.has(name):
            prompt = self.registry.get_full(name)
            return {
                'name': name,
                'length': len(prompt.get('template', '')),
                'has_variables': '$' in prompt.get('template', ''),
                'category': name.split('.')[0] if '.' in name else 'general'
            }
        return None

    def _clear_cache(self):
        """Clear the prompt cache"""
        self._cache.clear()

    def export_prompts(self, output_path: Path):
        """Export all prompts to a file for backup or versioning"""
        all_prompts = {}
        for name in self.registry.list_all():
            all_prompts[name] = self.registry.get_full(name)

        with open(output_path, 'w') as f:
            yaml.dump(all_prompts, f, default_flow_style=False)

        logger.info(f"Exported {len(all_prompts)} prompts to {output_path}")

    def import_prompts(self, input_path: Path, override: bool = False):
        """Import prompts from a backup file"""
        with open(input_path, 'r') as f:
            prompts = yaml.safe_load(f)

        for name, prompt_data in prompts.items():
            if isinstance(prompt_data, dict):
                template = prompt_data.get('template', prompt_data)
            else:
                template = prompt_data

            self.register_prompt(name, template, override=override)

        logger.info(f"Imported {len(prompts)} prompts from {input_path}")