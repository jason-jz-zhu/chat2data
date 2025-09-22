"""Dynamic query templates and patterns for SQL generation

This module provides schema-agnostic query templates that adapt to any database structure
instead of hardcoded e-commerce assumptions.
"""

from typing import Dict, List, Tuple, Optional, Any
import re
import logging

logger = logging.getLogger(__name__)


class QueryTemplates:
    """Dynamic query patterns and templates that adapt to any database schema"""

    def __init__(self, domain_adapter=None):
        """Initialize with optional domain adapter for dynamic content"""
        self.domain_adapter = domain_adapter
        self._dynamic_examples = []
        self._dynamic_column_mappings = {}
        self._dynamic_relationships = {}
        self._fallback_patterns = self._get_fallback_patterns()

    # Common query patterns with their SQL templates
    PATTERNS = [
        # Aggregation patterns
        {
            "pattern": r"(show|get|display|what is|calculate)?\s*(average|avg|mean)\s+(\w+)\s+(by|per|for each|group by)\s+(\w+)",
            "template": "SELECT {group_column}, AVG({value_column}) as average_{value_column} FROM {table} GROUP BY {group_column}",
            "example": "Show average price by category",
            "variables": ["value_column", "group_column"]
        },
        {
            "pattern": r"(show|get|display|what is)?\s*(total|sum)\s+(\w+)\s+(by|per|for each|group by)\s+(\w+)",
            "template": "SELECT {group_column}, SUM({value_column}) as total_{value_column} FROM {table} GROUP BY {group_column}",
            "example": "Show total sales by customer",
            "variables": ["value_column", "group_column"]
        },
        {
            "pattern": r"(count|how many)\s+(\w+)\s+(by|per|for each|group by)\s+(\w+)",
            "template": "SELECT {group_column}, COUNT(*) as count FROM {table} GROUP BY {group_column}",
            "example": "Count orders by status",
            "variables": ["group_column"]
        },

        # Top N patterns
        {
            "pattern": r"(top|first|highest|best)\s+(\d+)\s+(\w+)",
            "template": "SELECT * FROM {table} ORDER BY {order_column} DESC LIMIT {limit}",
            "example": "Top 5 expensive products",
            "variables": ["limit", "order_column"]
        },
        {
            "pattern": r"(bottom|last|lowest|cheapest)\s+(\d+)\s+(\w+)",
            "template": "SELECT * FROM {table} ORDER BY {order_column} ASC LIMIT {limit}",
            "example": "Bottom 10 products by price",
            "variables": ["limit", "order_column"]
        },

        # Join patterns
        {
            "pattern": r"(\w+)\s+with\s+(their|its)?\s*(\w+)",
            "template": "SELECT {t1}.*, {t2}.* FROM {table1} {t1} JOIN {table2} {t2} ON {t1}.{fk} = {t2}.{pk}",
            "example": "Orders with their customers",
            "variables": ["table1", "table2", "fk", "pk"]
        },

        # Filter patterns
        {
            "pattern": r"(\w+)\s+(with|where|having)\s+(\w+)\s*(>|<|=|>=|<=)\s*(\d+)",
            "template": "SELECT * FROM {table} WHERE {column} {operator} {value}",
            "example": "Products with stock > 10",
            "variables": ["column", "operator", "value"]
        }
    ]

    @property
    def FEW_SHOT_EXAMPLES(self) -> List[Dict[str, str]]:
        """Get dynamic few-shot examples based on schema analysis"""
        if self.domain_adapter and self.domain_adapter.is_adapted():
            # Get domain-adapted examples
            domain_config = self.domain_adapter.get_domain_configuration()
            if domain_config and domain_config.dynamic_templates:
                return [{
                    "question": ex.question,
                    "sql": ex.sql,
                    "explanation": ex.explanation
                } for ex in domain_config.dynamic_templates.few_shot_examples[:10]]

        # Return cached dynamic examples if available
        if self._dynamic_examples:
            return self._dynamic_examples

        # Fallback to minimal generic examples
        return self._get_fallback_examples()

    @property
    def COLUMN_MAPPINGS(self) -> Dict[str, str]:
        """Get dynamic column mappings based on schema analysis"""
        if self.domain_adapter and self.domain_adapter.is_adapted():
            # Get domain-adapted column mappings
            domain_config = self.domain_adapter.get_domain_configuration()
            if domain_config and domain_config.dynamic_templates:
                return domain_config.dynamic_templates.column_mappings

        # Return cached dynamic mappings if available
        if self._dynamic_column_mappings:
            return self._dynamic_column_mappings

        # Fallback to generic mappings
        return self._get_fallback_column_mappings()

    @property
    def TABLE_RELATIONSHIPS(self) -> Dict[Tuple[str, str], Dict[str, str]]:
        """Get dynamic table relationships based on schema analysis"""
        if self.domain_adapter and self.domain_adapter.is_adapted():
            # Get domain-adapted relationships
            domain_config = self.domain_adapter.get_domain_configuration()
            if domain_config and domain_config.dynamic_templates:
                relationships = {}
                for rel in domain_config.dynamic_templates.table_relationships:
                    key = (rel['from_table'], rel['to_table'])
                    relationships[key] = {
                        "join_condition": rel['join_condition'],
                        "foreign_key": rel['from_column'],
                        "primary_key": rel['to_column']
                    }
                return relationships

        # Return cached dynamic relationships if available
        if self._dynamic_relationships:
            return self._dynamic_relationships

        # Fallback to empty relationships (schema discovery will handle)
        return {}

    def get_formatted_examples(self) -> str:
        """Get formatted few-shot examples for prompt"""
        examples = []
        for example in self.FEW_SHOT_EXAMPLES:
            examples.append(f"Question: {example['question']}\nSQL: {example['sql']}")
        return "\n\n".join(examples)

    def get_relationship_description(self) -> str:
        """Get formatted table relationship descriptions"""
        descriptions = []
        for (table1, table2), rel in self.TABLE_RELATIONSHIPS.items():
            descriptions.append(f"• {table1} → {table2}: {rel['join_condition']}")
        return "\n".join(descriptions)

    def match_pattern(self, query: str) -> Dict[str, Any]:
        """Try to match query against known patterns"""
        query_lower = query.lower()

        # Use dynamic patterns if available, otherwise fallback patterns
        patterns = self._fallback_patterns

        for pattern_dict in patterns:
            match = re.search(pattern_dict["pattern"], query_lower)
            if match:
                return {
                    "matched": True,
                    "template": pattern_dict["template"],
                    "example": pattern_dict["example"],
                    "groups": match.groups()
                }

        return {"matched": False}

    def get_table_for_column(self, column: str) -> Optional[str]:
        """Infer table name from column reference using dynamic schema knowledge"""
        column_lower = column.lower()

        # Check dynamic column mappings first
        if column_lower in self.COLUMN_MAPPINGS:
            mapped = self.COLUMN_MAPPINGS[column_lower]
            if "." in mapped:
                return mapped.split(".")[0]

        # If domain adapter is available, use schema knowledge
        if self.domain_adapter and self.domain_adapter.is_adapted():
            domain_config = self.domain_adapter.get_domain_configuration()
            if domain_config and domain_config.schema_analysis:
                for table in domain_config.schema_analysis.tables:
                    for col in table.columns:
                        if col.name.lower() == column_lower:
                            return table.name

        return None

    def _get_fallback_patterns(self) -> List[Dict[str, Any]]:
        """Get generic fallback patterns that work with any schema"""
        return [
            # Generic aggregation patterns
            {
                "pattern": r"(show|get|display|what is|calculate)?\s*(average|avg|mean)\s+(\w+)\s+(by|per|for each|group by)\s+(\w+)",
                "template": "SELECT {group_column}, AVG({value_column}) as average_{value_column} FROM {table} GROUP BY {group_column}",
                "example": "Show average {value} by {category}",
                "variables": ["value_column", "group_column"]
            },
            {
                "pattern": r"(show|get|display|what is)?\s*(total|sum)\s+(\w+)\s+(by|per|for each|group by)\s+(\w+)",
                "template": "SELECT {group_column}, SUM({value_column}) as total_{value_column} FROM {table} GROUP BY {group_column}",
                "example": "Show total {value} by {category}",
                "variables": ["value_column", "group_column"]
            },
            {
                "pattern": r"(count|how many)\s+(\w+)\s+(by|per|for each|group by)\s+(\w+)",
                "template": "SELECT {group_column}, COUNT(*) as count FROM {table} GROUP BY {group_column}",
                "example": "Count {items} by {category}",
                "variables": ["group_column"]
            },
            # Generic top N patterns
            {
                "pattern": r"(top|first|highest|best)\s+(\d+)\s+(\w+)",
                "template": "SELECT * FROM {table} ORDER BY {order_column} DESC LIMIT {limit}",
                "example": "Top {n} {items}",
                "variables": ["limit", "order_column"]
            },
            {
                "pattern": r"(bottom|last|lowest|cheapest)\s+(\d+)\s+(\w+)",
                "template": "SELECT * FROM {table} ORDER BY {order_column} ASC LIMIT {limit}",
                "example": "Bottom {n} {items}",
                "variables": ["limit", "order_column"]
            },
            # Generic join patterns
            {
                "pattern": r"(\w+)\s+with\s+(their|its)?\s*(\w+)",
                "template": "SELECT {t1}.*, {t2}.* FROM {table1} {t1} JOIN {table2} {t2} ON {t1}.{fk} = {t2}.{pk}",
                "example": "{items} with their {related}",
                "variables": ["table1", "table2", "fk", "pk"]
            },
            # Generic filter patterns
            {
                "pattern": r"(\w+)\s+(with|where|having)\s+(\w+)\s*(>|<|=|>=|<=)\s*(\d+)",
                "template": "SELECT * FROM {table} WHERE {column} {operator} {value}",
                "example": "{items} with {attribute} {operator} {value}",
                "variables": ["column", "operator", "value"]
            }
        ]

    def _get_fallback_examples(self) -> List[Dict[str, str]]:
        """Get generic fallback examples when no domain adaptation is available"""
        return [
            {
                "question": "Show all records from the main table",
                "sql": "SELECT * FROM {main_table}",
                "explanation": "Simple SELECT all from main table"
            },
            {
                "question": "Count all records",
                "sql": "SELECT COUNT(*) as total_records FROM {main_table}",
                "explanation": "Count all rows in main table"
            },
            {
                "question": "Show recent records",
                "sql": "SELECT * FROM {main_table} ORDER BY {date_column} DESC LIMIT 10",
                "explanation": "Order by date column descending to get most recent records"
            }
        ]

    def _get_fallback_column_mappings(self) -> Dict[str, str]:
        """Get generic fallback column mappings"""
        return {
            "name": "{table}.name",
            "title": "{table}.title",
            "description": "{table}.description",
            "date": "{table}.created_at",
            "time": "{table}.created_at",
            "status": "{table}.status",
            "type": "{table}.type",
            "category": "{table}.category"
        }

    def set_dynamic_content(self, examples: List[Dict[str, str]],
                          column_mappings: Dict[str, str],
                          relationships: Dict[Tuple[str, str], Dict[str, str]]):
        """Set dynamic content manually (for testing or custom setups)"""
        self._dynamic_examples = examples
        self._dynamic_column_mappings = column_mappings
        self._dynamic_relationships = relationships
        logger.info(f"Set dynamic content: {len(examples)} examples, {len(column_mappings)} mappings, {len(relationships)} relationships")

    def clear_dynamic_content(self):
        """Clear all dynamic content and force fallback to generic patterns"""
        self._dynamic_examples = []
        self._dynamic_column_mappings = {}
        self._dynamic_relationships = {}
        logger.info("Cleared all dynamic content")

    def get_content_summary(self) -> Dict[str, Any]:
        """Get summary of current content source"""
        return {
            "source": "domain_adapted" if (self.domain_adapter and self.domain_adapter.is_adapted()) else "fallback",
            "examples_count": len(self.FEW_SHOT_EXAMPLES),
            "mappings_count": len(self.COLUMN_MAPPINGS),
            "relationships_count": len(self.TABLE_RELATIONSHIPS),
            "domain_adapter_available": self.domain_adapter is not None
        }