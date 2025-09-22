"""Semantic vector store provider using Ollama embeddings for better accuracy"""

import logging
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import requests
import json
from ...core.base import VectorStoreProvider, SchemaInfo
from ...core.query_templates import QueryTemplates
from ...config.central_config import get_config

logger = logging.getLogger(__name__)


class SemanticVectorStoreProvider(VectorStoreProvider):
    """Semantic vector store using Ollama embeddings for improved search"""

    def __init__(self, ollama_base_url: Optional[str] = None, embedding_model: Optional[str] = None):
        """Initialize semantic vector store with Ollama for embeddings"""
        config = get_config()
        self.ollama_base_url = ollama_base_url or config.vector_store.ollama_url
        self.embedding_model = embedding_model or config.vector_store.embedding_model
        self.schema_embeddings = {}  # table_name -> (text, embedding)
        self.query_embeddings = []  # List of (query, sql, embedding) tuples
        self.schema_data = {}

        logger.info(f"Initialized semantic vector store with Ollama URL: {self.ollama_base_url}, model: {self.embedding_model}")

    def _get_embedding(self, text: str) -> Optional[np.ndarray]:
        """Get embedding for text using Ollama"""
        try:
            response = requests.post(
                f"{self.ollama_base_url}/api/embeddings",
                json={
                    "model": self.embedding_model,
                    "prompt": text
                },
                timeout=30
            )
            if response.status_code == 200:
                embedding = response.json().get('embedding')
                if embedding:
                    return np.array(embedding)
        except Exception as e:
            logger.warning(f"Failed to get embedding from Ollama: {e}")
            # Fall back to simple hash-based pseudo-embeddings
            return self._get_fallback_embedding(text)

        return self._get_fallback_embedding(text)

    def _get_fallback_embedding(self, text: str) -> np.ndarray:
        """Generate a simple fallback embedding when Ollama is not available"""
        # Create a simple embedding based on character frequencies and keywords
        text_lower = text.lower()
        embedding = np.zeros(384)  # Fixed size embedding

        # Character-based features
        for i, char in enumerate(text_lower[:100]):  # First 100 chars
            embedding[ord(char) % 384] += 1

        # Keyword-based features
        keywords = ['select', 'from', 'where', 'join', 'group', 'order', 'count',
                   'sum', 'avg', 'max', 'min', 'table', 'column', 'product',
                   'customer', 'order', 'price', 'name', 'date', 'id']

        for i, keyword in enumerate(keywords):
            if keyword in text_lower:
                embedding[200 + i] += 5

        # Normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def search_relevant_schema(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant schema using semantic similarity"""
        query_embedding = self._get_embedding(query)

        if query_embedding is None:
            # Fallback to keyword matching
            return self._keyword_search(query, k)

        relevant_schemas = []

        # Calculate similarity with each table's embedding
        for table_name, (schema_text, table_embedding) in self.schema_embeddings.items():
            similarity = self._cosine_similarity(query_embedding, table_embedding)

            # Also check for exact table name matches for bonus points
            if table_name.lower() in query.lower():
                similarity += 0.3  # Bonus for exact match

            relevant_schemas.append({
                'schema': self.schema_data.get(table_name, {}),
                'relevance_score': similarity,
                'table_name': table_name
            })

        # Sort by relevance
        relevant_schemas.sort(key=lambda x: x['relevance_score'], reverse=True)

        # Return top k results
        return relevant_schemas[:k]

    def _keyword_search(self, query: str, k: int) -> List[Dict[str, Any]]:
        """Enhanced keyword-based search with QueryTemplates term mapping"""
        query_lower = query.lower()
        relevant_schemas = []

        # Use QueryTemplates to map common terms to specific columns/tables
        mapped_terms = self._map_query_terms(query_lower)

        for table_name, schema_info in self.schema_data.items():
            relevance_score = 0

            # Check if table name is mentioned
            if table_name.lower() in query_lower:
                relevance_score += 10

            # Check for mapped column references
            for mapped_term in mapped_terms:
                if table_name in mapped_term:
                    relevance_score += 8

            # Check column names
            if 'columns' in schema_info:
                for column in schema_info['columns']:
                    col_name = column.get('name', '').lower()
                    if col_name in query_lower:
                        relevance_score += 5

                    # Enhanced pattern matching using QueryTemplates
                    if 'price' in query_lower or 'cost' in query_lower:
                        if 'price' in col_name:
                            relevance_score += 5
                        if table_name == 'products':
                            relevance_score += 3

                    if 'category' in query_lower or 'group' in query_lower:
                        if 'category' in col_name:
                            relevance_score += 5
                        if table_name == 'categories':
                            relevance_score += 5

                    if 'average' in query_lower or 'avg' in query_lower:
                        if table_name in ['products', 'categories']:
                            relevance_score += 3

                    if 'customer' in query_lower:
                        if table_name == 'customers':
                            relevance_score += 5

                    if 'order' in query_lower and 'order' not in 'order by':
                        if table_name == 'orders':
                            relevance_score += 5

            if relevance_score > 0:
                relevant_schemas.append({
                    'schema': schema_info,
                    'relevance_score': relevance_score
                })

        relevant_schemas.sort(key=lambda x: x['relevance_score'], reverse=True)

        if not relevant_schemas:
            relevant_schemas = [{'schema': schema_info} for schema_info in self.schema_data.values()]

        return relevant_schemas[:k]

    def _map_query_terms(self, query_lower: str) -> List[str]:
        """Map query terms to database columns using QueryTemplates"""
        mapped_terms = []

        # Check each mapping in QueryTemplates
        for term, mapping in QueryTemplates.COLUMN_MAPPINGS.items():
            if term in query_lower:
                mapped_terms.append(mapping)

        return mapped_terms

    def index_schema(self, schema: List[SchemaInfo]) -> bool:
        """Index schema information with embeddings"""
        try:
            for schema_info in schema:
                # Create text representation of schema
                schema_text = self._create_schema_text(schema_info)

                # Get embedding
                embedding = self._get_embedding(schema_text)

                # Store everything
                self.schema_data[schema_info.name] = schema_info.model_dump()
                if embedding is not None:
                    self.schema_embeddings[schema_info.name] = (schema_text, embedding)

            logger.info(f"Indexed {len(schema)} tables with embeddings")
            return True

        except Exception as e:
            logger.error(f"Error indexing schema: {e}")
            return False

    def _create_schema_text(self, schema_info: SchemaInfo) -> str:
        """Create a text representation of schema for embedding"""
        text_parts = [
            f"Table: {schema_info.name}",
            f"Rows: {schema_info.row_count}"
        ]

        # Add column information
        for column in schema_info.columns:
            if isinstance(column, dict):
                col_text = f"Column: {column.get('name', 'Unknown')} Type: {column.get('type', 'Unknown')}"
                if column.get('primary_key'):
                    col_text += " PRIMARY KEY"
                if column.get('foreign_key'):
                    col_text += f" REFERENCES {column.get('foreign_key')}"
                text_parts.append(col_text)
            else:
                text_parts.append(f"Column: {column}")

        return " | ".join(text_parts)

    def store_query_example(self, query: str, sql: str) -> bool:
        """Store successful query examples with embeddings"""
        try:
            # Create combined text for embedding
            combined_text = f"Query: {query} SQL: {sql}"
            embedding = self._get_embedding(combined_text)

            if embedding is not None:
                self.query_embeddings.append((query, sql, embedding))

                # Keep only last 100 examples
                if len(self.query_embeddings) > 100:
                    self.query_embeddings = self.query_embeddings[-100:]

            return True

        except Exception as e:
            logger.error(f"Error storing query example: {e}")
            return False

    def get_similar_queries(self, query: str, k: int = 5) -> List[Tuple[str, str, float]]:
        """Get similar queries from history using semantic similarity

        Returns list of (query, sql, similarity_score) tuples
        """
        if not self.query_embeddings:
            return []

        query_embedding = self._get_embedding(query)
        if query_embedding is None:
            return []

        similar_queries = []

        for stored_query, stored_sql, stored_embedding in self.query_embeddings:
            similarity = self._cosine_similarity(query_embedding, stored_embedding)
            similar_queries.append((stored_query, stored_sql, similarity))

        # Sort by similarity
        similar_queries.sort(key=lambda x: x[2], reverse=True)

        return similar_queries[:k]

    def get_query_context(self, query: str) -> Dict[str, Any]:
        """Get enhanced context for query including relevant schemas and similar queries"""
        context = {
            'relevant_schemas': self.search_relevant_schema(query, k=3),
            'similar_queries': self.get_similar_queries(query, k=3),
            'all_tables': list(self.schema_data.keys())
        }

        return context

    @property
    def name(self) -> str:
        """Provider name"""
        return "Semantic Vector Store"