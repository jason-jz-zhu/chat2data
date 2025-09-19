"""
Chat2Data - Natural Language to SQL Framework

A professional framework for converting natural language queries to SQL
using local LLMs and vector databases.
"""

__version__ = "0.1.0"
__author__ = "Chat2Data Team"
__email__ = "team@chat2data.com"
__description__ = "Natural Language to SQL Framework using local LLMs and vector databases"

from .core.chat2data import Chat2Data
from .core.base import LLMProvider, DatabaseProvider, VectorStoreProvider
from .config.settings import Config

__all__ = [
    "Chat2Data",
    "LLMProvider",
    "DatabaseProvider",
    "VectorStoreProvider",
    "Config",
]