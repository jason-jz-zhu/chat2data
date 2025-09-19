"""Main Chat2Data framework class"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from .base import LLMProvider, DatabaseProvider, VectorStoreProvider, QueryResult, SchemaInfo

logger = logging.getLogger(__name__)


class Chat2Data:
    """Main Chat2Data framework class that orchestrates providers"""

    def __init__(
        self,
        llm_provider: LLMProvider,
        database_provider: DatabaseProvider,
        vector_store_provider: Optional[VectorStoreProvider] = None,
    ):
        """
        Initialize Chat2Data with providers

        Args:
            llm_provider: LLM provider for generating SQL
            database_provider: Database provider for executing queries
            vector_store_provider: Optional vector store for schema search
        """
        self.llm = llm_provider
        self.database = database_provider
        self.vector_store = vector_store_provider
        self._schema_indexed = False

    async def query(self, natural_language_query: str) -> Dict[str, Any]:
        """
        Process a natural language query and return results

        Args:
            natural_language_query: User's natural language query

        Returns:
            Dict with query results, SQL, and metadata
        """
        try:
            # Ensure schema is indexed
            if not self._schema_indexed:
                await self._ensure_schema_indexed()

            # Get relevant schema context
            schema_context = []
            if self.vector_store:
                schema_context = self.vector_store.search_relevant_schema(
                    natural_language_query
                )
            else:
                # Fallback: use all schema
                schema_info = self.database.get_schema()
                schema_context = [{"schema": info.model_dump()} for info in schema_info]

            # Generate SQL
            logger.info(f"Generating SQL for query: {natural_language_query}")
            sql = await self.llm.generate_sql(natural_language_query, schema_context)

            # Validate SQL
            is_safe, validation_message = self.database.validate_sql(sql)
            if not is_safe:
                return {
                    "success": False,
                    "query": natural_language_query,
                    "sql": sql,
                    "error": f"SQL validation failed: {validation_message}",
                }

            # Execute SQL
            logger.info(f"Executing SQL: {sql}")
            result = self.database.execute_query(sql)

            # Store successful query for learning
            if result.success and self.vector_store:
                self.vector_store.store_query_example(natural_language_query, sql)

            # Generate summary if we have data
            summary = None
            if result.success and result.data:
                try:
                    summary = await self.llm.generate_summary(
                        result.data, natural_language_query
                    )
                except Exception as e:
                    logger.warning(f"Failed to generate summary: {e}")

            return {
                "success": result.success,
                "query": natural_language_query,
                "sql": sql,
                "result": result.model_dump(),
                "summary": summary,
                "error": result.error,
            }

        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            return {
                "success": False,
                "query": natural_language_query,
                "error": str(e),
            }

    def get_schema(self) -> List[SchemaInfo]:
        """Get database schema information"""
        return self.database.get_schema()

    def get_similar_queries(self, query: str, k: int = 5) -> List[str]:
        """Get similar queries from history"""
        if self.vector_store:
            return self.vector_store.get_similar_queries(query, k)
        return []

    async def health_check(self) -> Dict[str, Any]:
        """Check health of all providers"""
        health = {
            "llm": {
                "name": self.llm.name,
                "available": self.llm.is_available(),
            },
            "database": {
                "name": self.database.name,
                "connected": self.database.is_connected(),
            },
        }

        if self.vector_store:
            health["vector_store"] = {
                "name": self.vector_store.name,
                "available": True,  # Assume available if instantiated
            }

        return health

    async def _ensure_schema_indexed(self):
        """Ensure database schema is indexed in vector store"""
        if self.vector_store and not self._schema_indexed:
            try:
                logger.info("Indexing database schema...")
                schema = self.database.get_schema()
                if schema:
                    self.vector_store.index_schema(schema)
                    self._schema_indexed = True
                    logger.info(f"Indexed {len(schema)} tables")
            except Exception as e:
                logger.warning(f"Failed to index schema: {e}")

    def force_reindex_schema(self):
        """Force re-indexing of schema"""
        self._schema_indexed = False