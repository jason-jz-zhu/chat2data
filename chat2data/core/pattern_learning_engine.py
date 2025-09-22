"""Pattern Learning Engine for Dynamic Query Pattern Management

This module provides a learning-based pattern storage and retrieval system
that replaces hardcoded query patterns with dynamic, adaptive patterns stored
in the vector database.
"""

import logging
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class QueryPattern:
    """Represents a query pattern stored in the vector database"""
    id: str
    query_text: str
    sql_template: str
    intent: str  # e.g., "list_all", "filter", "aggregate", "top_n"
    domain: str  # e.g., "ecommerce", "hr", "general"
    confidence_score: float
    success_count: int
    failure_count: int
    usage_count: int
    has_limit: bool
    limit_value: Optional[int]
    created_at: datetime
    updated_at: datetime
    user_feedback_score: float
    metadata: Dict[str, Any]

    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.5

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        return data


class PatternLearningEngine:
    """Manages query patterns in vector database with learning capabilities"""

    def __init__(self, vector_provider):
        """Initialize with vector database provider"""
        self.vector_provider = vector_provider
        self.collection_name = "query_patterns"
        self._initialize_collection()

    def _initialize_collection(self):
        """Initialize pattern collection in vector database"""
        try:
            # Create or get the patterns collection
            logger.info(f"Initializing query patterns collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Error initializing patterns collection: {e}")

    async def store_pattern(
        self,
        query_text: str,
        sql_template: str,
        intent: str,
        domain: str = "general",
        has_limit: bool = False,
        limit_value: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> QueryPattern:
        """Store a new query pattern in the vector database"""
        pattern = QueryPattern(
            id=self._generate_pattern_id(query_text, sql_template),
            query_text=query_text,
            sql_template=sql_template,
            intent=intent,
            domain=domain,
            confidence_score=0.5,  # Start with neutral confidence
            success_count=0,
            failure_count=0,
            usage_count=0,
            has_limit=has_limit,
            limit_value=limit_value,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            user_feedback_score=0.0,
            metadata=metadata or {}
        )

        # Generate embedding for the query text
        embedding = await self.vector_provider.embed_text(query_text)

        # Store in vector database
        await self.vector_provider.store_embedding(
            collection=self.collection_name,
            id=pattern.id,
            embedding=embedding,
            metadata=pattern.to_dict()
        )

        logger.info(f"Stored pattern: {pattern.id} - {intent}")
        return pattern

    async def find_similar_patterns(
        self,
        query: str,
        domain: Optional[str] = None,
        k: int = 5,
        min_confidence: float = 0.3
    ) -> List[QueryPattern]:
        """Find similar patterns using vector similarity search"""
        # Generate embedding for the query
        query_embedding = await self.vector_provider.embed_text(query)

        # Build filter conditions
        filters = {"confidence_score": {"$gte": min_confidence}}
        if domain:
            filters["domain"] = domain

        # Search for similar patterns
        results = await self.vector_provider.search_embeddings(
            collection=self.collection_name,
            query_embedding=query_embedding,
            k=k * 2,  # Get more results for filtering
            filter=filters
        )

        # Convert results to QueryPattern objects
        patterns = []
        for result in results:
            metadata = result.get('metadata', {})
            pattern = self._metadata_to_pattern(metadata)
            if pattern:
                patterns.append(pattern)

        # Sort by relevance score * confidence score
        patterns.sort(
            key=lambda p: p.confidence_score * p.success_rate,
            reverse=True
        )

        return patterns[:k]

    async def update_pattern_feedback(
        self,
        pattern_id: str,
        success: bool,
        user_feedback: Optional[float] = None
    ):
        """Update pattern based on usage feedback"""
        # Retrieve current pattern
        pattern_data = await self.vector_provider.get_by_id(
            collection=self.collection_name,
            id=pattern_id
        )

        if not pattern_data:
            logger.warning(f"Pattern not found: {pattern_id}")
            return

        metadata = pattern_data.get('metadata', {})

        # Update counts
        if success:
            metadata['success_count'] = metadata.get('success_count', 0) + 1
        else:
            metadata['failure_count'] = metadata.get('failure_count', 0) + 1

        metadata['usage_count'] = metadata.get('usage_count', 0) + 1

        # Update confidence score using exponential moving average
        success_rate = metadata['success_count'] / (metadata['success_count'] + metadata['failure_count'])
        alpha = 0.1  # Learning rate
        metadata['confidence_score'] = (1 - alpha) * metadata.get('confidence_score', 0.5) + alpha * success_rate

        # Update user feedback score if provided
        if user_feedback is not None:
            current_feedback = metadata.get('user_feedback_score', 0.0)
            feedback_count = metadata.get('usage_count', 1)
            metadata['user_feedback_score'] = (current_feedback * (feedback_count - 1) + user_feedback) / feedback_count

        metadata['updated_at'] = datetime.now().isoformat()

        # Update in vector database
        await self.vector_provider.update_metadata(
            collection=self.collection_name,
            id=pattern_id,
            metadata=metadata
        )

        logger.info(f"Updated pattern {pattern_id}: success={success}, confidence={metadata['confidence_score']:.3f}")

    async def learn_from_correction(
        self,
        original_query: str,
        incorrect_sql: str,
        corrected_sql: str,
        domain: str = "general"
    ):
        """Learn from user corrections to SQL queries"""
        # Analyze the correction
        has_limit = "LIMIT" in corrected_sql.upper()
        limit_value = self._extract_limit_value(corrected_sql) if has_limit else None

        # Determine intent from the corrected SQL
        intent = self._analyze_sql_intent(corrected_sql)

        # Store the corrected pattern with high initial confidence
        pattern = await self.store_pattern(
            query_text=original_query,
            sql_template=self._generalize_sql(corrected_sql),
            intent=intent,
            domain=domain,
            has_limit=has_limit,
            limit_value=limit_value,
            metadata={
                "learned_from_correction": True,
                "original_sql": incorrect_sql,
                "correction_timestamp": datetime.now().isoformat()
            }
        )

        # Boost confidence for corrected patterns
        pattern.confidence_score = 0.8
        pattern.success_count = 1

        logger.info(f"Learned from correction: {original_query} -> {intent}")

    def _analyze_sql_intent(self, sql: str) -> str:
        """Analyze SQL to determine its intent"""
        sql_upper = sql.upper()

        if "COUNT(*)" in sql_upper:
            return "count"
        elif "AVG(" in sql_upper or "SUM(" in sql_upper:
            return "aggregate"
        elif "GROUP BY" in sql_upper:
            return "group"
        elif "ORDER BY" in sql_upper and "LIMIT" in sql_upper:
            limit_value = self._extract_limit_value(sql)
            if limit_value and limit_value <= 10:
                return "top_n"
        elif "WHERE" in sql_upper:
            return "filter"
        elif "JOIN" in sql_upper:
            return "join"
        elif "LIMIT" not in sql_upper and "SELECT *" in sql_upper:
            return "list_all"
        else:
            return "general"

    def _extract_limit_value(self, sql: str) -> Optional[int]:
        """Extract LIMIT value from SQL"""
        import re
        match = re.search(r'LIMIT\s+(\d+)', sql, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

    def _generalize_sql(self, sql: str) -> str:
        """Generalize SQL to create a reusable template"""
        import re

        # Replace specific table names with placeholders
        sql = re.sub(r'\bFROM\s+(\w+)', r'FROM {table}', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bJOIN\s+(\w+)', r'JOIN {join_table}', sql, flags=re.IGNORECASE)

        # Replace specific column names in WHERE clauses
        sql = re.sub(r'WHERE\s+(\w+)\s*=\s*["\']?[\w\s]+["\']?', r'WHERE {column} = {value}', sql, flags=re.IGNORECASE)

        # Keep LIMIT values as is (important for learning)
        # Don't generalize LIMIT because we want to learn specific limits

        return sql

    def _generate_pattern_id(self, query: str, sql: str) -> str:
        """Generate unique ID for pattern"""
        import hashlib
        content = f"{query}:{sql}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _metadata_to_pattern(self, metadata: Dict[str, Any]) -> Optional[QueryPattern]:
        """Convert metadata dict to QueryPattern object"""
        try:
            # Parse datetime strings
            metadata['created_at'] = datetime.fromisoformat(metadata['created_at'])
            metadata['updated_at'] = datetime.fromisoformat(metadata['updated_at'])
            return QueryPattern(**metadata)
        except Exception as e:
            logger.error(f"Error converting metadata to pattern: {e}")
            return None

    async def migrate_hardcoded_patterns(self, patterns: List[Dict[str, Any]]):
        """Migrate hardcoded patterns to vector database"""
        logger.info(f"Migrating {len(patterns)} hardcoded patterns to vector DB")

        for pattern_data in patterns:
            # Determine if pattern has limit
            sql_template = pattern_data.get('template', '')
            has_limit = '{limit}' in sql_template or 'LIMIT' in sql_template

            # For "list_all" patterns, explicitly set no limit
            if pattern_data.get('name', '').startswith('list_all'):
                has_limit = False
                # Remove LIMIT from template
                sql_template = sql_template.replace(' LIMIT {limit}', '')

            await self.store_pattern(
                query_text=pattern_data.get('example', ''),
                sql_template=sql_template,
                intent=pattern_data.get('name', 'general'),
                domain=pattern_data.get('domain', 'general'),
                has_limit=has_limit,
                limit_value=pattern_data.get('default_limit'),
                metadata={
                    "migrated_from_hardcoded": True,
                    "original_pattern": pattern_data
                }
            )

    async def get_pattern_statistics(self) -> Dict[str, Any]:
        """Get statistics about stored patterns"""
        # This would query the vector DB for statistics
        stats = {
            "total_patterns": 0,
            "patterns_by_intent": {},
            "patterns_by_domain": {},
            "average_confidence": 0.0,
            "most_successful_patterns": [],
            "recently_learned": []
        }

        # Implementation would query vector DB
        return stats