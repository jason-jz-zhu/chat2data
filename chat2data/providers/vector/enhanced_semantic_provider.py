"""Enhanced Semantic Vector Store with Pattern Learning Support

This provider extends the basic semantic vector store to include
pattern storage and retrieval for the Pattern Learning Engine.
"""

import logging
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import requests
import json
import hashlib
from datetime import datetime
from ...core.base import VectorStoreProvider, SchemaInfo

logger = logging.getLogger(__name__)


class EnhancedSemanticVectorProvider(VectorStoreProvider):
    """Enhanced semantic vector store with pattern learning capabilities"""

    def __init__(self, ollama_base_url: Optional[str] = None, embedding_model: Optional[str] = None):
        """Initialize enhanced semantic vector store"""
        from ...config.central_config import get_config
        config = get_config()
        self.ollama_base_url = ollama_base_url or config.vector_store.ollama_url
        self.embedding_model = embedding_model or config.vector_store.embedding_model

        # Original schema storage
        self.schema_embeddings = {}  # table_name -> (text, embedding)
        self.schema_data = {}

        # Pattern storage - separate collections for different types
        self.pattern_collections = {
            "query_patterns": {},  # pattern_id -> (metadata, embedding)
            "successful_queries": {},  # query_id -> (metadata, embedding)
            "user_corrections": {}  # correction_id -> (metadata, embedding)
        }

        logger.info(f"Initialized enhanced semantic vector store with pattern learning support")

    async def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for text using Ollama"""
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

        # Fallback to simple embedding
        return self._get_fallback_embedding(text)

    def _get_fallback_embedding(self, text: str) -> np.ndarray:
        """Generate fallback embedding when Ollama is unavailable"""
        text_lower = text.lower()
        embedding = np.zeros(384)

        # Character-based features
        for i, char in enumerate(text_lower[:100]):
            embedding[ord(char) % 384] += 1

        # SQL keyword features
        sql_keywords = ['select', 'from', 'where', 'join', 'group', 'order',
                       'limit', 'count', 'sum', 'avg', 'all', 'distinct']

        for i, keyword in enumerate(sql_keywords):
            if keyword in text_lower:
                embedding[200 + i] += 5

        # Special handling for "all" vs "limit"
        if 'all' in text_lower and 'limit' not in text_lower:
            embedding[350] = 10  # Strong signal for no limit
        elif 'limit' in text_lower:
            embedding[351] = 10  # Strong signal for limit

        # Normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding

    async def store_embedding(
        self,
        collection: str,
        id: str,
        embedding: np.ndarray,
        metadata: Dict[str, Any]
    ):
        """Store an embedding in the specified collection"""
        if collection not in self.pattern_collections:
            self.pattern_collections[collection] = {}

        self.pattern_collections[collection][id] = {
            "embedding": embedding,
            "metadata": metadata
        }

        logger.debug(f"Stored embedding in {collection}: {id}")

    async def search_embeddings(
        self,
        collection: str,
        query_embedding: np.ndarray,
        k: int = 5,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar embeddings in a collection"""
        if collection not in self.pattern_collections:
            return []

        results = []

        for item_id, item_data in self.pattern_collections[collection].items():
            # Apply filters if provided
            if filter and not self._matches_filter(item_data['metadata'], filter):
                continue

            # Calculate similarity
            similarity = self._cosine_similarity(query_embedding, item_data['embedding'])

            results.append({
                'id': item_id,
                'similarity': similarity,
                'metadata': item_data['metadata']
            })

        # Sort by similarity
        results.sort(key=lambda x: x['similarity'], reverse=True)

        return results[:k]

    async def get_by_id(self, collection: str, id: str) -> Optional[Dict[str, Any]]:
        """Retrieve an item by ID from a collection"""
        if collection in self.pattern_collections:
            if id in self.pattern_collections[collection]:
                return self.pattern_collections[collection][id]
        return None

    async def update_metadata(
        self,
        collection: str,
        id: str,
        metadata: Dict[str, Any]
    ):
        """Update metadata for an existing embedding"""
        if collection in self.pattern_collections:
            if id in self.pattern_collections[collection]:
                self.pattern_collections[collection][id]['metadata'] = metadata
                logger.debug(f"Updated metadata in {collection}: {id}")

    def _matches_filter(self, metadata: Dict[str, Any], filter: Dict[str, Any]) -> bool:
        """Check if metadata matches the filter criteria"""
        for key, value in filter.items():
            if key not in metadata:
                return False

            # Handle comparison operators
            if isinstance(value, dict):
                if '$gte' in value:
                    if metadata[key] < value['$gte']:
                        return False
                if '$lte' in value:
                    if metadata[key] > value['$lte']:
                        return False
                if '$eq' in value:
                    if metadata[key] != value['$eq']:
                        return False
            else:
                if metadata[key] != value:
                    return False

        return True

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    # Original methods for schema search (backward compatibility)
    def search_relevant_schema(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant schema using semantic similarity"""
        query_embedding = self._get_fallback_embedding(query)

        relevant_schemas = []

        for table_name, (schema_text, table_embedding) in self.schema_embeddings.items():
            similarity = self._cosine_similarity(query_embedding, table_embedding)

            if table_name.lower() in query.lower():
                similarity += 0.3

            relevant_schemas.append({
                'schema': self.schema_data.get(table_name, {}),
                'relevance_score': similarity,
                'table_name': table_name
            })

        relevant_schemas.sort(key=lambda x: x['relevance_score'], reverse=True)
        return relevant_schemas[:k]

    def store_schema(self, schema_info: SchemaInfo):
        """Store schema information with embeddings"""
        table_name = schema_info.table_name

        # Create descriptive text for embedding
        schema_text = f"Table: {table_name}\n"

        if schema_info.columns:
            schema_text += f"Columns: {', '.join([col.name for col in schema_info.columns])}\n"

        if schema_info.sample_queries:
            schema_text += f"Sample queries: {'; '.join(schema_info.sample_queries[:3])}"

        # Generate and store embedding
        embedding = self._get_fallback_embedding(schema_text)

        self.schema_embeddings[table_name] = (schema_text, embedding)
        self.schema_data[table_name] = {
            'name': table_name,
            'columns': [{'name': col.name, 'type': col.type} for col in schema_info.columns] if schema_info.columns else [],
            'sample_queries': schema_info.sample_queries
        }

        logger.info(f"Stored schema embedding for table: {table_name}")

    @property
    def name(self) -> str:
        """Provider name"""
        return "Enhanced Semantic Vector Store with Pattern Learning"

    def get_stored_patterns_count(self) -> Dict[str, int]:
        """Get count of stored patterns by collection"""
        return {
            collection: len(patterns)
            for collection, patterns in self.pattern_collections.items()
        }

    async def clear_collection(self, collection: str):
        """Clear all items in a collection"""
        if collection in self.pattern_collections:
            self.pattern_collections[collection] = {}
            logger.info(f"Cleared collection: {collection}")