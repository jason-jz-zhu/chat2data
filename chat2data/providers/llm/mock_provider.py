"""Mock LLM provider for demo mode - no external dependencies"""

import re
import random
from typing import Dict, List, Any, Optional
from ...core.base import LLMProvider
from ...core.query_templates import QueryTemplates


class MockLLMProvider(LLMProvider):
    """Mock LLM provider that generates domain-adaptive SQL queries for demo purposes"""

    def __init__(self, domain_adapter=None):
        """Initialize mock provider with optional domain adapter"""
        self.domain_adapter = domain_adapter
        self.query_templates = QueryTemplates(domain_adapter)
        self._last_schema_context = None
        self._schema_aware_patterns = {}

    def set_domain_adapter(self, domain_adapter):
        """Set domain adapter for dynamic behavior"""
        self.domain_adapter = domain_adapter
        self.query_templates = QueryTemplates(domain_adapter)
        self._schema_aware_patterns = {}

    def _build_schema_aware_patterns(self, schema_context: List[Dict[str, Any]]) -> Dict[str, str]:
        """Build query patterns based on actual schema context"""
        patterns = {}

        # Extract table and column information from schema
        available_tables = []
        table_columns = {}

        for context in schema_context:
            if 'schema' in context and 'name' in context['schema']:
                table_name = context['schema']['name']
                available_tables.append(table_name)

                # Extract column information
                columns = []
                if 'columns' in context['schema']:
                    for col in context['schema']['columns']:
                        if isinstance(col, dict):
                            columns.append(col.get('name', ''))
                        else:
                            columns.append(str(col))
                table_columns[table_name] = columns

        if not available_tables:
            # Fallback to generic table names if no schema provided
            available_tables = ['table1', 'main_table', 'data']
            table_columns = {
                'table1': ['id', 'name', 'value'],
                'main_table': ['id', 'name', 'value'],
                'data': ['id', 'name', 'value']
            }

        # Build patterns dynamically based on available tables
        primary_table = available_tables[0]

        # Basic count patterns
        for table in available_tables:
            table_singular = table.rstrip('s') if table.endswith('s') else table
            patterns[f'(?i).*count.*{table}'] = f"SELECT COUNT(*) as {table}_count FROM {table}"
            patterns[f'(?i).*count.*{table_singular}'] = f"SELECT COUNT(*) as {table}_count FROM {table}"
            patterns[f'(?i).*how.*many.*{table}'] = f"SELECT COUNT(*) as {table}_count FROM {table}"
            patterns[f'(?i).*number.*of.*{table}'] = f"SELECT COUNT(*) as {table}_count FROM {table}"

        # Basic list/show patterns
        for table in available_tables:
            table_singular = table.rstrip('s') if table.endswith('s') else table
            patterns[f'(?i).*show.*all.*{table}'] = f"SELECT * FROM {table} LIMIT 50"
            patterns[f'(?i).*list.*all.*{table}'] = f"SELECT * FROM {table} LIMIT 50"
            patterns[f'(?i).*list.*{table}'] = f"SELECT * FROM {table} LIMIT 50"
            patterns[f'(?i).*all.*{table}'] = f"SELECT * FROM {table} LIMIT 50"
            patterns[f'(?i).*show.*{table}'] = f"SELECT * FROM {table} LIMIT 50"
            patterns[f'(?i).*get.*{table}'] = f"SELECT * FROM {table} LIMIT 50"
            patterns[f'(?i).*display.*{table}'] = f"SELECT * FROM {table} LIMIT 50"

        # Find potential numeric columns for aggregations
        numeric_columns = []
        for table, columns in table_columns.items():
            for col in columns:
                col_lower = col.lower()
                if any(keyword in col_lower for keyword in ['price', 'amount', 'cost', 'value', 'quantity', 'count', 'total', 'sum', 'number']):
                    numeric_columns.append((table, col))

        # Build aggregation patterns for numeric columns
        for table, col in numeric_columns:
            patterns[f'(?i).*total.*{col}'] = f"SELECT SUM({col}) as total_{col} FROM {table}"
            patterns[f'(?i).*sum.*{col}'] = f"SELECT SUM({col}) as total_{col} FROM {table}"
            patterns[f'(?i).*average.*{col}'] = f"SELECT AVG({col}) as average_{col} FROM {table}"
            patterns[f'(?i).*avg.*{col}'] = f"SELECT AVG({col}) as average_{col} FROM {table}"
            patterns[f'(?i).*max.*{col}'] = f"SELECT MAX({col}) as max_{col} FROM {table}"
            patterns[f'(?i).*min.*{col}'] = f"SELECT MIN({col}) as min_{col} FROM {table}"

        # Try to use QueryTemplates patterns if available
        try:
            template_match = self.query_templates.match_pattern("")
            if template_match.get("matched"):
                # Query templates are available, use them for additional patterns
                pass
        except Exception:
            pass

        return patterns

    async def generate_sql(self, query: str, schema_context: List[Dict[str, Any]]) -> str:
        """Generate SQL from natural language query using schema-aware pattern matching"""

        # Rebuild patterns if schema context changed
        if schema_context != self._last_schema_context:
            self._schema_aware_patterns = self._build_schema_aware_patterns(schema_context)
            self._last_schema_context = schema_context

        # Try QueryTemplates pattern matching first
        try:
            template_match = self.query_templates.match_pattern(query)
            if template_match.get("matched"):
                # Use the template pattern if available
                template = template_match["template"]

                # Try to fill in the template with actual table/column names
                if schema_context:
                    available_tables = []
                    for context in schema_context:
                        if 'schema' in context and 'name' in context['schema']:
                            available_tables.append(context['schema']['name'])

                    if available_tables:
                        # Simple template variable substitution
                        filled_template = template.replace("{table}", available_tables[0])
                        return filled_template

                return template
        except Exception:
            pass

        # Check for schema-aware pattern matches
        for pattern, sql in self._schema_aware_patterns.items():
            if re.match(pattern, query):
                return sql

        # Extract table names from schema context for fallback
        available_tables = []
        table_columns = {}

        for context in schema_context:
            if 'schema' in context and 'name' in context['schema']:
                table_name = context['schema']['name']
                available_tables.append(table_name)

                # Extract column information
                columns = []
                if 'columns' in context['schema']:
                    for col in context['schema']['columns']:
                        if isinstance(col, dict):
                            columns.append(col.get('name', ''))
                        else:
                            columns.append(str(col))
                table_columns[table_name] = columns

        # Fallback to first available table or generic table
        primary_table = available_tables[0] if available_tables else 'main_table'

        # Smart fallback query generation based on keywords
        query_lower = query.lower()

        if any(word in query_lower for word in ['count', 'number', 'how many']):
            return f"SELECT COUNT(*) as count FROM {primary_table}"

        elif any(word in query_lower for word in ['sum', 'total']):
            # Find a potential numeric column
            numeric_col = self._find_numeric_column(table_columns.get(primary_table, []), query_lower)
            return f"SELECT SUM({numeric_col}) as total FROM {primary_table}"

        elif any(word in query_lower for word in ['average', 'avg']):
            numeric_col = self._find_numeric_column(table_columns.get(primary_table, []), query_lower)
            return f"SELECT AVG({numeric_col}) as average FROM {primary_table}"

        elif any(word in query_lower for word in ['max', 'maximum', 'highest']):
            numeric_col = self._find_numeric_column(table_columns.get(primary_table, []), query_lower)
            return f"SELECT MAX({numeric_col}) as maximum FROM {primary_table}"

        elif any(word in query_lower for word in ['min', 'minimum', 'lowest']):
            numeric_col = self._find_numeric_column(table_columns.get(primary_table, []), query_lower)
            return f"SELECT MIN({numeric_col}) as minimum FROM {primary_table}"

        elif any(word in query_lower for word in ['recent', 'latest', 'new']):
            # Try to find a date column
            date_col = self._find_date_column(table_columns.get(primary_table, []))
            return f"SELECT * FROM {primary_table} ORDER BY {date_col} DESC LIMIT 20"

        else:
            # Default to SELECT * with limit
            return f"SELECT * FROM {primary_table} LIMIT 20"

    def _find_numeric_column(self, columns: List[str], query: str) -> str:
        """Find the most appropriate numeric column for aggregation"""
        if not columns:
            return "id"

        # Look for columns mentioned in the query
        for col in columns:
            if col.lower() in query:
                return col

        # Look for common numeric column patterns
        numeric_patterns = ['price', 'amount', 'cost', 'value', 'quantity', 'count', 'total', 'sum', 'number']
        for pattern in numeric_patterns:
            for col in columns:
                if pattern in col.lower():
                    return col

        # Fallback to first column or id
        return columns[0] if columns else "id"

    def _find_date_column(self, columns: List[str]) -> str:
        """Find the most appropriate date column for ordering"""
        if not columns:
            return "id"

        # Look for common date column patterns
        date_patterns = ['created_at', 'updated_at', 'date', 'time', 'timestamp', 'created', 'modified']
        for pattern in date_patterns:
            for col in columns:
                if pattern in col.lower():
                    return col

        # Fallback to first column or id
        return columns[0] if columns else "id"

    async def generate_summary(self, data: List[Dict[str, Any]], query: str) -> str:
        """Generate a domain-adaptive summary of the results"""
        if not data:
            return "No results found for your query."

        row_count = len(data)

        # Get context-aware summary templates
        if self.domain_adapter and self.domain_adapter.is_adapted():
            try:
                domain_config = self.domain_adapter.get_domain_configuration()
                if domain_config and hasattr(domain_config, 'summary_templates'):
                    # Use domain-specific summary templates if available
                    templates = domain_config.summary_templates
                    if templates:
                        return random.choice(templates).format(count=row_count, query=query)
            except Exception:
                pass

        # Generic summary templates
        base_summaries = [
            f"Found {row_count} results for your query.",
            f"Your query returned {row_count} rows of data.",
            f"Retrieved {row_count} records matching your criteria.",
        ]

        # Add context based on query
        query_lower = query.lower()
        if 'total' in query_lower or 'sum' in query_lower:
            if row_count == 1 and data[0]:
                first_value = list(data[0].values())[0]
                base_summaries.append(f"The total calculated value is {first_value}.")
        elif 'count' in query_lower:
            if row_count == 1 and data[0]:
                first_value = list(data[0].values())[0]
                base_summaries.append(f"The count is {first_value}.")
        elif 'average' in query_lower or 'avg' in query_lower:
            if row_count == 1 and data[0]:
                first_value = list(data[0].values())[0]
                if isinstance(first_value, (int, float)):
                    base_summaries.append(f"The average value is {first_value:.2f}.")
                else:
                    base_summaries.append(f"The average value is {first_value}.")

        return random.choice(base_summaries)

    def is_available(self) -> bool:
        """Mock provider is always available"""
        return True

    @property
    def name(self) -> str:
        """Provider name"""
        return "Mock LLM Provider (Domain-Adaptive)"