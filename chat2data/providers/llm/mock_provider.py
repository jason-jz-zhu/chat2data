"""Mock LLM provider for demo mode - no external dependencies"""

import re
import random
from typing import Dict, List, Any
from ...core.base import LLMProvider


class MockLLMProvider(LLMProvider):
    """Mock LLM provider that generates simple SQL queries for demo purposes"""

    def __init__(self):
        """Initialize mock provider"""
        self._query_patterns = {
            # Most specific patterns first - order matters!
            # Count/aggregation patterns need to come before generic product patterns
            r'(?i).*count.*products?': "SELECT COUNT(*) as product_count FROM products",
            r'(?i).*count.*orders?': "SELECT COUNT(*) as order_count FROM orders",
            r'(?i).*total.*sales?': "SELECT SUM(total_amount) as total_sales FROM orders",

            # Expensive/cheap product patterns
            r'(?i).*top.*\d+.*expensive.*products?': "SELECT * FROM products ORDER BY price DESC LIMIT 5",
            r'(?i).*top.*expensive.*products?': "SELECT * FROM products ORDER BY price DESC LIMIT 5",
            r'(?i).*most.*expensive.*products?': "SELECT * FROM products ORDER BY price DESC LIMIT 5",
            r'(?i).*expensive.*products?': "SELECT * FROM products ORDER BY price DESC LIMIT 10",

            # Basic patterns for common queries
            r'(?i).*show.*all.*products?': "SELECT * FROM products LIMIT 50",
            r'(?i).*list.*products?': "SELECT * FROM products LIMIT 50",
            r'(?i).*all.*products?': "SELECT * FROM products LIMIT 50",
            r'(?i).*average.*price': "SELECT AVG(price) as average_price FROM products",
            r'(?i).*cheap.*products?': "SELECT * FROM products ORDER BY price ASC LIMIT 10",
            r'(?i).*sales.*by.*category': "SELECT c.name as category, SUM(p.price * oi.quantity) as total_sales FROM products p JOIN order_items oi ON p.id = oi.product_id JOIN categories c ON p.category_id = c.id GROUP BY c.id, c.name",
            r'(?i).*low.*stock': "SELECT * FROM products WHERE stock_quantity < 10",
            r'(?i).*out.*stock': "SELECT * FROM products WHERE stock_quantity = 0",
            r'(?i).*recent.*orders?': "SELECT * FROM orders ORDER BY created_at DESC LIMIT 20",
            r'(?i).*customers?.*orders?': "SELECT c.name, COUNT(o.id) as order_count FROM customers c LEFT JOIN orders o ON c.id = o.customer_id GROUP BY c.id, c.name",
            r'(?i).*sales.*trends?': "SELECT DATE(created_at) as date, COUNT(*) as orders FROM orders GROUP BY DATE(created_at) ORDER BY date",
        }

    async def generate_sql(self, query: str, schema_context: List[Dict[str, Any]]) -> str:
        """Generate SQL from natural language query using pattern matching"""

        # Check for pattern matches
        for pattern, sql in self._query_patterns.items():
            if re.match(pattern, query):
                return sql

        # Extract table names from schema context
        available_tables = []
        for context in schema_context:
            if 'schema' in context and 'name' in context['schema']:
                available_tables.append(context['schema']['name'])

        # Default fallback based on common table names
        if not available_tables:
            available_tables = ['products', 'orders', 'customers', 'categories']

        # Generate a reasonable fallback query
        primary_table = available_tables[0] if available_tables else 'products'

        # Simple keyword-based query generation
        query_lower = query.lower()

        if any(word in query_lower for word in ['count', 'number', 'how many']):
            return f"SELECT COUNT(*) as count FROM {primary_table}"
        elif any(word in query_lower for word in ['sum', 'total']):
            # Try to find a numeric column name
            numeric_cols = ['price', 'amount', 'quantity', 'value', 'cost']
            col = next((col for col in numeric_cols if col in query_lower), 'id')
            return f"SELECT SUM({col}) as total FROM {primary_table}"
        elif any(word in query_lower for word in ['average', 'avg']):
            numeric_cols = ['price', 'amount', 'quantity', 'value', 'cost']
            col = next((col for col in numeric_cols if col in query_lower), 'price')
            return f"SELECT AVG({col}) as average FROM {primary_table}"
        elif any(word in query_lower for word in ['max', 'maximum', 'highest']):
            numeric_cols = ['price', 'amount', 'quantity', 'value', 'cost']
            col = next((col for col in numeric_cols if col in query_lower), 'price')
            return f"SELECT MAX({col}) as maximum FROM {primary_table}"
        elif any(word in query_lower for word in ['min', 'minimum', 'lowest']):
            numeric_cols = ['price', 'amount', 'quantity', 'value', 'cost']
            col = next((col for col in numeric_cols if col in query_lower), 'price')
            return f"SELECT MIN({col}) as minimum FROM {primary_table}"
        else:
            # Default to SELECT * with limit
            return f"SELECT * FROM {primary_table} LIMIT 20"

    async def generate_summary(self, data: List[Dict[str, Any]], query: str) -> str:
        """Generate a simple summary of the results"""
        if not data:
            return "No results found for your query."

        row_count = len(data)

        # Basic summary templates
        summaries = [
            f"Found {row_count} results for your query.",
            f"Your query returned {row_count} rows of data.",
            f"Retrieved {row_count} records matching your criteria.",
        ]

        # Add context based on query
        query_lower = query.lower()
        if 'total' in query_lower or 'sum' in query_lower:
            if row_count == 1 and data[0]:
                first_value = list(data[0].values())[0]
                summaries.append(f"The total calculated value is {first_value}.")
        elif 'count' in query_lower:
            if row_count == 1 and data[0]:
                first_value = list(data[0].values())[0]
                summaries.append(f"The count is {first_value}.")
        elif 'average' in query_lower or 'avg' in query_lower:
            if row_count == 1 and data[0]:
                first_value = list(data[0].values())[0]
                summaries.append(f"The average value is {first_value:.2f}.")

        return random.choice(summaries)

    def is_available(self) -> bool:
        """Mock provider is always available"""
        return True

    @property
    def name(self) -> str:
        """Provider name"""
        return "Mock LLM Provider"