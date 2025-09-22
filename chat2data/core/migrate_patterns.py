#!/usr/bin/env python
"""Migration script to move hardcoded patterns to vector database

This script migrates all hardcoded query patterns from dynamic_template_generator.py
to the vector database using the PatternLearningEngine, removing hardcoded LIMIT clauses
for "show all" type queries.
"""

import asyncio
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


async def migrate_patterns_to_vector_db():
    """Migrate hardcoded patterns to vector database"""
    from chat2data.core.pattern_learning_engine import PatternLearningEngine
    from chat2data.providers.vector.enhanced_semantic_provider import EnhancedSemanticVectorProvider

    # Initialize the vector provider and pattern engine
    vector_provider = EnhancedSemanticVectorProvider()
    pattern_engine = PatternLearningEngine(vector_provider)

    # Define base patterns WITHOUT hardcoded limits for "show all" queries
    base_patterns = [
        # List all patterns - NO LIMIT!
        {
            'name': 'list_all',
            'template': 'SELECT * FROM {table}',  # No LIMIT!
            'example': 'Show all products',
            'intent': 'list_all',
            'phrases': ['show all', 'list all', 'get all', 'display all', 'view all'],
            'has_limit': False,
            'domain': 'general'
        },
        {
            'name': 'list_all_categories',
            'template': 'SELECT * FROM categories',  # No LIMIT!
            'example': 'Show all categories',
            'intent': 'list_all',
            'phrases': ['show all categories', 'list all categories', 'display all categories'],
            'has_limit': False,
            'domain': 'ecommerce'
        },

        # Count patterns
        {
            'name': 'count_all',
            'template': 'SELECT COUNT(*) as total FROM {table}',
            'example': 'Count all products',
            'intent': 'count',
            'phrases': ['count all', 'how many', 'total number of'],
            'has_limit': False,
            'domain': 'general'
        },

        # Top N patterns - These DO have limits
        {
            'name': 'top_n',
            'template': 'SELECT * FROM {table} ORDER BY {column} DESC LIMIT {n}',
            'example': 'Top 5 expensive products',
            'intent': 'top_n',
            'phrases': ['top', 'highest', 'most expensive', 'largest', 'biggest'],
            'has_limit': True,
            'default_limit': 5,
            'domain': 'general'
        },
        {
            'name': 'bottom_n',
            'template': 'SELECT * FROM {table} ORDER BY {column} ASC LIMIT {n}',
            'example': 'Bottom 10 products by price',
            'intent': 'bottom_n',
            'phrases': ['bottom', 'lowest', 'cheapest', 'smallest', 'least expensive'],
            'has_limit': True,
            'default_limit': 10,
            'domain': 'general'
        },

        # Filter patterns
        {
            'name': 'filter_by_column',
            'template': 'SELECT * FROM {table} WHERE {column} = {value}',
            'example': 'Show products where category is electronics',
            'intent': 'filter',
            'phrases': ['show', 'find', 'get', 'where', 'filter by'],
            'has_limit': False,
            'domain': 'general'
        },
        {
            'name': 'range_filter',
            'template': 'SELECT * FROM {table} WHERE {column} BETWEEN {min_val} AND {max_val}',
            'example': 'Products with price between 10 and 100',
            'intent': 'range_filter',
            'phrases': ['between', 'from', 'range', 'in the range'],
            'has_limit': False,
            'domain': 'general'
        },

        # Aggregation patterns
        {
            'name': 'average_by_category',
            'template': 'SELECT {category_column}, AVG({numeric_column}) as average FROM {table} GROUP BY {category_column}',
            'example': 'Show average price by category',
            'intent': 'aggregate',
            'phrases': ['average by', 'avg by', 'mean by'],
            'has_limit': False,
            'domain': 'general'
        },
        {
            'name': 'sum_by_category',
            'template': 'SELECT {category_column}, SUM({numeric_column}) as total FROM {table} GROUP BY {category_column}',
            'example': 'Show total sales by category',
            'intent': 'aggregate',
            'phrases': ['sum by', 'total by', 'aggregate by'],
            'has_limit': False,
            'domain': 'general'
        },
        {
            'name': 'count_by_category',
            'template': 'SELECT {category_column}, COUNT(*) as count FROM {table} GROUP BY {category_column}',
            'example': 'Count orders by status',
            'intent': 'aggregate',
            'phrases': ['count by', 'number by', 'group by'],
            'has_limit': False,
            'domain': 'general'
        },

        # Join patterns
        {
            'name': 'join_tables',
            'template': 'SELECT {t1}.*, {t2}.* FROM {table1} {t1} JOIN {table2} {t2} ON {t1}.{fk} = {t2}.{pk}',
            'example': 'Show orders with their customers',
            'intent': 'join',
            'phrases': ['with their', 'and their', 'including', 'along with', 'join'],
            'has_limit': False,
            'domain': 'general'
        },

        # Temporal patterns
        {
            'name': 'recent_records',
            'template': 'SELECT * FROM {table} WHERE {date_column} >= DATE_SUB(NOW(), INTERVAL {period})',
            'example': 'Show recent orders from last week',
            'intent': 'temporal',
            'phrases': ['recent', 'last', 'past', 'since', 'from last'],
            'has_limit': False,
            'domain': 'general'
        },

        # Special patterns for common queries
        {
            'name': 'show_first_n',
            'template': 'SELECT * FROM {table} LIMIT {n}',
            'example': 'Show first 10 products',
            'intent': 'limit',
            'phrases': ['first', 'show some', 'limit to', 'just show'],
            'has_limit': True,
            'default_limit': 10,
            'domain': 'general'
        }
    ]

    # Migrate each pattern
    logger.info(f"Starting migration of {len(base_patterns)} patterns to vector DB")

    for pattern_data in base_patterns:
        try:
            # Extract pattern details
            for phrase in pattern_data.get('phrases', []):
                await pattern_engine.store_pattern(
                    query_text=phrase,
                    sql_template=pattern_data['template'],
                    intent=pattern_data['intent'],
                    domain=pattern_data.get('domain', 'general'),
                    has_limit=pattern_data.get('has_limit', False),
                    limit_value=pattern_data.get('default_limit'),
                    metadata={
                        'pattern_name': pattern_data['name'],
                        'example': pattern_data.get('example', ''),
                        'migrated': True,
                        'confidence_boost': 0.7  # Give migrated patterns decent initial confidence
                    }
                )

            logger.info(f"Migrated pattern: {pattern_data['name']}")

        except Exception as e:
            logger.error(f"Failed to migrate pattern {pattern_data['name']}: {e}")

    # Add some learned patterns for "show all" to reinforce no LIMIT behavior
    learned_patterns = [
        {
            'query': 'show me all categories',
            'sql': 'SELECT * FROM categories',
            'intent': 'list_all'
        },
        {
            'query': 'display all products',
            'sql': 'SELECT * FROM products',
            'intent': 'list_all'
        },
        {
            'query': 'list all customers',
            'sql': 'SELECT * FROM customers',
            'intent': 'list_all'
        },
        {
            'query': 'get all orders',
            'sql': 'SELECT * FROM orders',
            'intent': 'list_all'
        }
    ]

    for learned in learned_patterns:
        await pattern_engine.store_pattern(
            query_text=learned['query'],
            sql_template=learned['sql'],
            intent=learned['intent'],
            domain='general',
            has_limit=False,  # Explicitly NO limit
            metadata={
                'learned_pattern': True,
                'confidence_boost': 0.9  # High confidence for learned patterns
            }
        )

    logger.info("Pattern migration completed successfully")

    # Print statistics
    stats = await pattern_engine.get_pattern_statistics()
    logger.info(f"Migration statistics: {stats}")

    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(migrate_patterns_to_vector_db())