"""Prompt Registry for storing and managing prompt templates"""
import logging
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from copy import deepcopy

logger = logging.getLogger(__name__)


class PromptRegistry:
    """
    Registry for storing and managing prompt templates.
    Supports hierarchical organization, versioning, and metadata.
    """

    def __init__(self):
        """Initialize an empty prompt registry"""
        self._prompts: Dict[str, Dict[str, Any]] = {}
        self._versions: Dict[str, List[Dict[str, Any]]] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}

    def register(self,
                 name: str,
                 prompt: Union[str, Dict[str, Any]],
                 metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Register a new prompt in the registry.

        Args:
            name: Unique identifier for the prompt (e.g., 'sql_generation.enhanced')
            prompt: The prompt template string or dictionary with template and metadata
            metadata: Optional metadata about the prompt

        Returns:
            True if registered successfully
        """
        try:
            # Normalize prompt data
            if isinstance(prompt, str):
                prompt_data = {
                    'template': prompt,
                    'created_at': datetime.now().isoformat(),
                    'version': 1
                }
            else:
                prompt_data = deepcopy(prompt)
                if 'template' not in prompt_data:
                    if 'base' in prompt_data:
                        # Handle different naming conventions
                        prompt_data['template'] = prompt_data.pop('base')
                    else:
                        prompt_data['template'] = str(prompt)

                prompt_data['created_at'] = datetime.now().isoformat()
                prompt_data['version'] = prompt_data.get('version', 1)

            # Store previous version if updating
            if name in self._prompts:
                self._store_version(name, self._prompts[name])
                prompt_data['version'] = self._prompts[name].get('version', 0) + 1

            # Store prompt
            self._prompts[name] = prompt_data

            # Store metadata
            if metadata:
                self._metadata[name] = {
                    **metadata,
                    'updated_at': datetime.now().isoformat()
                }

            logger.debug(f"Registered prompt: {name} (version {prompt_data['version']})")
            return True

        except Exception as e:
            logger.error(f"Error registering prompt {name}: {e}")
            return False

    def get(self, name: str, version: Optional[int] = None) -> Optional[str]:
        """
        Get a prompt template by name.

        Args:
            name: Prompt identifier
            version: Optional version number (defaults to latest)

        Returns:
            The prompt template string or None if not found
        """
        if version is not None:
            # Get specific version
            versions = self._versions.get(name, [])
            for v in versions:
                if v.get('version') == version:
                    return v.get('template')

        # Get current version
        if name in self._prompts:
            prompt_data = self._prompts[name]
            template = prompt_data.get('template', '')

            # Handle composite prompts
            if isinstance(prompt_data, dict):
                # Build full prompt from parts if needed
                parts = []

                # Add base template
                if 'template' in prompt_data:
                    parts.append(prompt_data['template'])
                elif 'base' in prompt_data:
                    parts.append(prompt_data['base'])

                # Add safety rules if present
                if 'safety_rules' in prompt_data:
                    if isinstance(prompt_data['safety_rules'], list):
                        rules = '\n'.join(f"- {rule}" for rule in prompt_data['safety_rules'])
                        parts.append(f"\nSafety Rules:\n{rules}")
                    else:
                        parts.append(f"\n{prompt_data['safety_rules']}")

                # Add examples if present
                if 'examples' in prompt_data:
                    if isinstance(prompt_data['examples'], list):
                        examples = '\n'.join(prompt_data['examples'])
                        parts.append(f"\nExamples:\n{examples}")

                template = '\n'.join(parts)

            return template

        # Try parent category if not found
        if '.' in name:
            parent = name.rsplit('.', 1)[0]
            return self.get(parent)

        return None

    def get_full(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get full prompt data including metadata.

        Args:
            name: Prompt identifier

        Returns:
            Complete prompt dictionary or None if not found
        """
        return deepcopy(self._prompts.get(name))

    def has(self, name: str) -> bool:
        """
        Check if a prompt exists in the registry.

        Args:
            name: Prompt identifier

        Returns:
            True if prompt exists
        """
        return name in self._prompts

    def list_all(self, prefix: Optional[str] = None) -> List[str]:
        """
        List all prompt names, optionally filtered by prefix.

        Args:
            prefix: Optional prefix to filter prompts

        Returns:
            List of prompt names
        """
        if prefix:
            return [name for name in self._prompts.keys() if name.startswith(prefix)]
        return list(self._prompts.keys())

    def list_categories(self) -> List[str]:
        """
        List all prompt categories (first part of hierarchical names).

        Returns:
            List of unique category names
        """
        categories = set()
        for name in self._prompts.keys():
            if '.' in name:
                category = name.split('.')[0]
                categories.add(category)
            else:
                categories.add('general')
        return sorted(list(categories))

    def remove(self, name: str) -> bool:
        """
        Remove a prompt from the registry.

        Args:
            name: Prompt identifier

        Returns:
            True if removed successfully
        """
        if name in self._prompts:
            # Store as version before removing
            self._store_version(name, self._prompts[name])
            del self._prompts[name]

            if name in self._metadata:
                del self._metadata[name]

            logger.debug(f"Removed prompt: {name}")
            return True

        return False

    def _store_version(self, name: str, prompt_data: Dict[str, Any]):
        """Store a version of the prompt for history"""
        if name not in self._versions:
            self._versions[name] = []

        version_data = deepcopy(prompt_data)
        version_data['archived_at'] = datetime.now().isoformat()
        self._versions[name].append(version_data)

        # Keep only last 10 versions
        if len(self._versions[name]) > 10:
            self._versions[name] = self._versions[name][-10:]

    def get_versions(self, name: str) -> List[Dict[str, Any]]:
        """
        Get version history for a prompt.

        Args:
            name: Prompt identifier

        Returns:
            List of previous versions
        """
        return deepcopy(self._versions.get(name, []))

    def merge_registry(self, other: 'PromptRegistry', override: bool = False):
        """
        Merge another registry into this one.

        Args:
            other: Another PromptRegistry instance
            override: Whether to override existing prompts
        """
        for name in other.list_all():
            if not self.has(name) or override:
                prompt_data = other.get_full(name)
                if prompt_data:
                    self.register(name, prompt_data)

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the registry"""
        return {
            'total_prompts': len(self._prompts),
            'categories': self.list_categories(),
            'versioned_prompts': len(self._versions),
            'total_versions': sum(len(v) for v in self._versions.values()),
            'prompts_with_metadata': len(self._metadata)
        }

    def clear(self):
        """Clear all prompts from the registry"""
        self._prompts.clear()
        self._versions.clear()
        self._metadata.clear()

    def __repr__(self) -> str:
        """String representation of the registry"""
        stats = self.get_stats()
        return (f"PromptRegistry(prompts={stats['total_prompts']}, "
                f"categories={len(stats['categories'])})")

    def __len__(self) -> int:
        """Number of prompts in registry"""
        return len(self._prompts)