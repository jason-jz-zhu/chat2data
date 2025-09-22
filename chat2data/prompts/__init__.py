"""Centralized Prompt Management System for Chat2Data"""

from .manager import PromptManager
from .registry import PromptRegistry

__all__ = ['PromptManager', 'PromptRegistry']

# Global prompt manager instance (singleton pattern)
_prompt_manager = None


def get_prompt_manager() -> PromptManager:
    """
    Get the global PromptManager instance.
    Uses singleton pattern to ensure consistent prompt management.

    Returns:
        The global PromptManager instance
    """
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager