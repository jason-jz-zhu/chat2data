"""Mock LLM provider for demo mode - no external dependencies"""

import re
import random
from typing import Dict, List, Any, Optional
from ...core.base import LLMProvider


class MockLLMProvider(LLMProvider):
    """Simplified Mock LLM provider for reliable demo purposes"""

    def __init__(self):
        """Initialize mock provider"""
        self._dangerous_keywords = [
            'DELETE', 'DROP', 'INSERT', 'UPDATE', 'TRUNCATE',
            'ALTER', 'CREATE', 'EXEC', 'EXECUTE', 'GRANT', 'REVOKE'
        ]

    def _check_security(self, query: str) -> bool:
        """Check if query contains dangerous keywords"""
        query_upper = query.upper()
        for keyword in self._dangerous_keywords:
            if keyword in query_upper:
                return False
        return True

    def _get_table_names(self, schema_context: List[Dict[str, Any]]) -> List[str]:
        """Extract table names from schema context"""
        tables = []
        for context in schema_context:
            if 'schema' in context and 'name' in context['schema']:
                tables.append(context['schema']['name'])
        return tables if tables else ['data']

    def _get_columns_for_table(self, table_name: str, schema_context: List[Dict[str, Any]]) -> List[str]:
        """Get column names for a specific table"""
        for context in schema_context:
            if 'schema' in context and context['schema'].get('name') == table_name:
                columns = []
                if 'columns' in context['schema']:
                    for col in context['schema']['columns']:
                        if isinstance(col, dict):
                            columns.append(col.get('name', ''))
                return columns
        return ['id', 'name']  # Fallback columns

    async def generate_sql(self, query: str, schema_context: List[Dict[str, Any]]) -> str:
        """Generate SQL from natural language query with security checks"""

        # Security check first
        if not self._check_security(query):
            raise ValueError(f"Query contains dangerous operations and cannot be executed for security reasons")

        # Get available tables
        tables = self._get_table_names(schema_context)
        primary_table = tables[0]  # Use first table as primary

        query_lower = query.lower().strip()

        # Pattern matching for different query types

        # COUNT queries
        if any(keyword in query_lower for keyword in ['count', 'how many', 'number']):
            if 'customer' in query_lower:
                return "SELECT COUNT(*) as customers_count FROM customers"
            elif 'product' in query_lower:
                return "SELECT COUNT(*) as products_count FROM products"
            elif 'order' in query_lower:
                return "SELECT COUNT(*) as orders_count FROM orders"
            else:
                return f"SELECT COUNT(*) as count FROM {primary_table}"

        # SHOW/LIST queries
        elif any(keyword in query_lower for keyword in ['show', 'list', 'display', 'get']) and any(keyword in query_lower for keyword in ['all', 'products', 'customers', 'orders']):
            if 'product' in query_lower:
                return "SELECT * FROM products LIMIT 50"
            elif 'customer' in query_lower:
                return "SELECT * FROM customers LIMIT 50"
            elif 'order' in query_lower:
                return "SELECT * FROM orders LIMIT 50"
            else:
                return f"SELECT * FROM {primary_table} LIMIT 50"

        # TOP/EXPENSIVE queries
        elif any(keyword in query_lower for keyword in ['top', 'expensive', 'highest', 'best']):
            if 'product' in query_lower:
                return "SELECT * FROM products ORDER BY price DESC LIMIT 5"
            else:
                # Find a numeric column to order by
                numeric_col = self._find_numeric_column(self._get_columns_for_table(primary_table, schema_context))
                return f"SELECT * FROM {primary_table} ORDER BY {numeric_col} DESC LIMIT 5"

        # SUM/TOTAL queries
        elif any(keyword in query_lower for keyword in ['sum', 'total']):
            if 'sales' in query_lower or 'revenue' in query_lower:
                return "SELECT SUM(total_amount) as total_revenue FROM orders"
            elif 'price' in query_lower:
                return "SELECT SUM(price) as total_price FROM products"
            else:
                # Find a numeric column to sum
                numeric_col = self._find_numeric_column(self._get_columns_for_table(primary_table, schema_context))
                return f"SELECT SUM({numeric_col}) as total FROM {primary_table}"

        # AVERAGE queries
        elif any(keyword in query_lower for keyword in ['average', 'avg']):
            if 'price' in query_lower:
                return "SELECT AVG(price) as average_price FROM products"
            else:
                numeric_col = self._find_numeric_column(self._get_columns_for_table(primary_table, schema_context))
                return f"SELECT AVG({numeric_col}) as average FROM {primary_table}"

        # Default fallback
        else:
            return f"SELECT * FROM {primary_table} LIMIT 20"

    def _find_numeric_column(self, columns: List[str]) -> str:
        """Find the most appropriate numeric column for aggregation"""
        if not columns:
            return "id"

        # Look for common numeric column patterns
        numeric_patterns = ['price', 'amount', 'cost', 'value', 'quantity', 'count', 'total', 'sum', 'number']
        for pattern in numeric_patterns:
            for col in columns:
                if pattern in col.lower():
                    return col

        # Fallback to id
        return "id"

    async def generate_summary(self, data: List[Dict[str, Any]], query: str) -> str:
        """Generate a simple, reliable summary of the results"""
        if not data:
            return "No results found for your query."

        row_count = len(data)
        query_lower = query.lower()

        # Specific summaries for different query types
        if 'count' in query_lower:
            if row_count == 1 and data[0]:
                count_value = list(data[0].values())[0]
                return f"Found {count_value} records matching your criteria."
        elif any(keyword in query_lower for keyword in ['total', 'sum']):
            if row_count == 1 and data[0]:
                total_value = list(data[0].values())[0]
                return f"The total calculated value is {total_value}."
        elif any(keyword in query_lower for keyword in ['average', 'avg']):
            if row_count == 1 and data[0]:
                avg_value = list(data[0].values())[0]
                return f"The average value is {avg_value}."

        # Default summary
        return f"Retrieved {row_count} records matching your criteria."

    def is_available(self) -> bool:
        """Mock provider is always available"""
        return True

    @property
    def name(self) -> str:
        """Provider name"""
        return "Mock LLM Provider (Secure & Reliable)"