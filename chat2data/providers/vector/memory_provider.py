"""In-memory vector store provider for Chat2Data (no external dependencies)"""

import logging
from typing import Dict, List, Any
from ...core.base import VectorStoreProvider, SchemaInfo

logger = logging.getLogger(__name__)


class MemoryVectorStoreProvider(VectorStoreProvider):
    """Simple in-memory vector store for demo purposes"""

    def __init__(self):
        """Initialize memory vector store"""
        self.schema_data = {}
        self.query_examples = []

    def search_relevant_schema(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant schema based on query using simple keyword matching"""
        query_lower = query.lower()
        relevant_schemas = []

        # Simple keyword-based relevance scoring
        for table_name, schema_info in self.schema_data.items():
            relevance_score = 0

            # Check if table name is mentioned
            if table_name.lower() in query_lower:
                relevance_score += 10

            # Check column names
            for column in schema_info['columns']:
                col_name = column['name'].lower()
                if col_name in query_lower:
                    relevance_score += 5

                # Check for common patterns
                if 'price' in query_lower and 'price' in col_name:
                    relevance_score += 3
                if any(word in query_lower for word in ['count', 'number']) and 'id' in col_name:
                    relevance_score += 3
                if 'name' in query_lower and 'name' in col_name:
                    relevance_score += 3
                if 'date' in query_lower and ('date' in col_name or 'time' in col_name):
                    relevance_score += 3

            if relevance_score > 0:
                relevant_schemas.append({
                    'schema': schema_info,
                    'relevance_score': relevance_score
                })

        # Sort by relevance and return top k
        relevant_schemas.sort(key=lambda x: x['relevance_score'], reverse=True)

        # If no relevant schemas found, return all schemas
        if not relevant_schemas:
            relevant_schemas = [{'schema': schema_info} for schema_info in self.schema_data.values()]

        return relevant_schemas[:k]

    def index_schema(self, schema: List[SchemaInfo]) -> bool:
        """Index schema information"""
        try:
            for schema_info in schema:
                self.schema_data[schema_info.name] = schema_info.model_dump()
            logger.info(f"Indexed {len(schema)} tables in memory vector store")
            return True
        except Exception as e:
            logger.error(f"Error indexing schema: {e}")
            return False

    def store_query_example(self, query: str, sql: str) -> bool:
        """Store successful query examples"""
        try:
            self.query_examples.append({
                'query': query,
                'sql': sql
            })
            # Keep only last 100 examples
            if len(self.query_examples) > 100:
                self.query_examples = self.query_examples[-100:]
            return True
        except Exception as e:
            logger.error(f"Error storing query example: {e}")
            return False

    def get_similar_queries(self, query: str, k: int = 5) -> List[str]:
        """Get similar queries from history using simple keyword matching"""
        query_lower = query.lower()
        query_words = set(query_lower.split())

        similar_queries = []
        for example in self.query_examples:
            example_words = set(example['query'].lower().split())

            # Calculate simple word overlap
            overlap = len(query_words.intersection(example_words))
            if overlap > 0:
                similar_queries.append({
                    'query': example['query'],
                    'overlap': overlap
                })

        # Sort by overlap and return top k
        similar_queries.sort(key=lambda x: x['overlap'], reverse=True)
        return [item['query'] for item in similar_queries[:k]]

    @property
    def name(self) -> str:
        """Provider name"""
        return "Memory Vector Store"