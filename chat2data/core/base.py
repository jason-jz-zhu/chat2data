"""Base provider interfaces for Chat2Data"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple
from pydantic import BaseModel


class QueryResult(BaseModel):
    """Standard query result structure"""
    success: bool
    data: Optional[List[Dict[str, Any]]] = None
    columns: Optional[List[str]] = None
    row_count: int = 0
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SchemaInfo(BaseModel):
    """Database schema information"""
    name: str
    columns: List[Dict[str, Any]]
    row_count: Optional[int] = None
    description: Optional[str] = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""

    @abstractmethod
    async def generate_sql(self, query: str, schema_context: List[Dict[str, Any]]) -> str:
        """Generate SQL from natural language query"""
        pass

    @abstractmethod
    async def generate_summary(self, data: List[Dict[str, Any]], query: str) -> str:
        """Generate natural language summary of results"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name"""
        pass


class DatabaseProvider(ABC):
    """Abstract base class for database providers"""

    @abstractmethod
    def execute_query(self, sql: str) -> QueryResult:
        """Execute SQL query and return results"""
        pass

    @abstractmethod
    def get_schema(self) -> List[SchemaInfo]:
        """Get database schema information"""
        pass

    @abstractmethod
    def validate_sql(self, sql: str) -> Tuple[bool, str]:
        """Validate SQL for safety"""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if database is connected"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name"""
        pass


class VectorStoreProvider(ABC):
    """Abstract base class for vector store providers"""

    @abstractmethod
    def search_relevant_schema(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant schema based on query"""
        pass

    @abstractmethod
    def index_schema(self, schema: List[SchemaInfo]) -> bool:
        """Index schema information"""
        pass

    @abstractmethod
    def store_query_example(self, query: str, sql: str) -> bool:
        """Store successful query examples"""
        pass

    @abstractmethod
    def get_similar_queries(self, query: str, k: int = 5) -> List[str]:
        """Get similar queries from history"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name"""
        pass