"""Dynamic Template Generator for Chat2Data Framework

Automatically generates query patterns, few-shot examples, and column mappings
based on schema analysis results from any database.
"""

import logging
import re
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass
from collections import defaultdict

from .schema_discovery import SchemaAnalysis, TableAnalysis, ColumnAnalysis, ColumnType

logger = logging.getLogger(__name__)


@dataclass
class QueryPattern:
    """A dynamic query pattern generated from schema analysis"""
    pattern_name: str
    template: str
    example_queries: List[str]
    required_tables: List[str]
    required_columns: List[str]
    confidence: float


@dataclass
class FewShotExample:
    """A few-shot example generated for specific schema"""
    question: str
    sql: str
    explanation: str
    pattern_type: str
    confidence: float


@dataclass
class DynamicQueryTemplates:
    """Complete set of dynamic templates for a specific schema"""
    schema_name: str
    patterns: List[QueryPattern]
    few_shot_examples: List[FewShotExample]
    column_mappings: Dict[str, str]
    table_relationships: List[Dict[str, Any]]
    common_phrases: Dict[str, str]


class DynamicTemplateGenerator:
    """Generates query templates and examples based on schema analysis"""

    def __init__(self):
        """Initialize the template generator"""
        # Base patterns that can be adapted to any schema
        self.base_patterns = {
            'list_all': {
                'template': 'SELECT * FROM {table} LIMIT {limit}',
                'phrases': ['show all', 'list all', 'get all', 'display all']
            },
            'count_all': {
                'template': 'SELECT COUNT(*) as total FROM {table}',
                'phrases': ['count all', 'how many', 'total number of']
            },
            'filter_by_column': {
                'template': 'SELECT * FROM {table} WHERE {column} = {value}',
                'phrases': ['show', 'find', 'get', 'where']
            },
            'aggregate_by_category': {
                'template': 'SELECT {category_column}, {aggregation}({numeric_column}) FROM {main_table} {join_clause} GROUP BY {category_column}',
                'phrases': ['average by', 'sum by', 'count by', 'total by', 'group by']
            },
            'top_n': {
                'template': 'SELECT * FROM {table} ORDER BY {column} DESC LIMIT {n}',
                'phrases': ['top', 'highest', 'most expensive', 'largest', 'biggest']
            },
            'bottom_n': {
                'template': 'SELECT * FROM {table} ORDER BY {column} ASC LIMIT {n}',
                'phrases': ['bottom', 'lowest', 'cheapest', 'smallest']
            },
            'range_filter': {
                'template': 'SELECT * FROM {table} WHERE {column} BETWEEN {min_val} AND {max_val}',
                'phrases': ['between', 'from', 'range']
            },
            'comparison_filter': {
                'template': 'SELECT * FROM {table} WHERE {column} {operator} {value}',
                'phrases': ['greater than', 'less than', 'more than', 'below', 'above']
            },
            'join_tables': {
                'template': 'SELECT {select_columns} FROM {main_table} {join_type} JOIN {related_table} ON {join_condition}',
                'phrases': ['with their', 'and their', 'including', 'along with']
            },
            'temporal_queries': {
                'template': 'SELECT * FROM {table} WHERE {date_column} {date_operator} {date_value}',
                'phrases': ['last', 'this', 'recent', 'since', 'before', 'after']
            }
        }

        # Pattern mappings for different aggregations
        self.aggregation_mappings = {
            'average': 'AVG',
            'avg': 'AVG',
            'mean': 'AVG',
            'sum': 'SUM',
            'total': 'SUM',
            'count': 'COUNT',
            'number': 'COUNT',
            'max': 'MAX',
            'maximum': 'MAX',
            'highest': 'MAX',
            'min': 'MIN',
            'minimum': 'MIN',
            'lowest': 'MIN'
        }

        # Comparison operator mappings
        self.comparison_mappings = {
            'greater than': '>',
            'more than': '>',
            'above': '>',
            'over': '>',
            'less than': '<',
            'below': '<',
            'under': '<',
            'at least': '>=',
            'minimum': '>=',
            'at most': '<=',
            'maximum': '<=',
            'equal to': '=',
            'equals': '=',
            'is': '='
        }

    def generate_templates(self, schema_analysis: SchemaAnalysis) -> DynamicQueryTemplates:
        """Generate complete set of templates for a schema"""
        try:
            logger.info(f"Generating dynamic templates for schema: {schema_analysis.database_name}")

            # Generate patterns for this schema
            patterns = self._generate_patterns(schema_analysis)

            # Generate few-shot examples
            few_shot_examples = self._generate_few_shot_examples(schema_analysis, patterns)

            # Generate column mappings
            column_mappings = self._generate_column_mappings(schema_analysis)

            # Extract table relationships
            table_relationships = self._format_relationships(schema_analysis)

            # Generate common phrases mapping
            common_phrases = self._generate_phrase_mappings(schema_analysis)

            templates = DynamicQueryTemplates(
                schema_name=schema_analysis.database_name,
                patterns=patterns,
                few_shot_examples=few_shot_examples,
                column_mappings=column_mappings,
                table_relationships=table_relationships,
                common_phrases=common_phrases
            )

            logger.info(f"Generated {len(patterns)} patterns and {len(few_shot_examples)} examples")
            return templates

        except Exception as e:
            logger.error(f"Error generating templates: {e}")
            raise

    def _generate_patterns(self, schema_analysis: SchemaAnalysis) -> List[QueryPattern]:
        """Generate query patterns based on schema structure"""
        patterns = []

        for table in schema_analysis.tables:
            if table.table_type == 'entity':  # Focus on main entity tables
                patterns.extend(self._generate_table_patterns(table, schema_analysis))

        # Generate cross-table patterns
        patterns.extend(self._generate_relationship_patterns(schema_analysis))

        # Generate aggregation patterns
        patterns.extend(self._generate_aggregation_patterns(schema_analysis))

        return patterns

    def _generate_table_patterns(self, table: TableAnalysis, schema_analysis: SchemaAnalysis) -> List[QueryPattern]:
        """Generate patterns for a specific table"""
        patterns = []
        table_name = table.name

        # Basic list pattern
        patterns.append(QueryPattern(
            pattern_name=f"list_all_{table_name}",
            template=f"SELECT * FROM {table_name} LIMIT {{limit}}",
            example_queries=[
                f"Show all {table_name}",
                f"List all {table_name}",
                f"Display all {table_name}"
            ],
            required_tables=[table_name],
            required_columns=[],
            confidence=0.9
        ))

        # Count pattern
        patterns.append(QueryPattern(
            pattern_name=f"count_{table_name}",
            template=f"SELECT COUNT(*) as total FROM {table_name}",
            example_queries=[
                f"Count all {table_name}",
                f"How many {table_name}?",
                f"Total number of {table_name}"
            ],
            required_tables=[table_name],
            required_columns=[],
            confidence=0.9
        ))

        # Patterns based on column types
        for column in table.columns:
            if column.semantic_type == ColumnType.AMOUNT:
                # Top/bottom by amount
                patterns.append(QueryPattern(
                    pattern_name=f"top_{table_name}_by_{column.name}",
                    template=f"SELECT * FROM {table_name} ORDER BY {column.name} DESC LIMIT {{n}}",
                    example_queries=[
                        f"Top {table_name} by {column.name}",
                        f"Most expensive {table_name}",
                        f"Highest {column.name} {table_name}"
                    ],
                    required_tables=[table_name],
                    required_columns=[column.name],
                    confidence=0.8
                ))

            elif column.semantic_type == ColumnType.STATUS:
                # Filter by status
                patterns.append(QueryPattern(
                    pattern_name=f"filter_{table_name}_by_{column.name}",
                    template=f"SELECT * FROM {table_name} WHERE {column.name} = '{{value}}'",
                    example_queries=[
                        f"Show {table_name} with {column.name}",
                        f"Filter {table_name} by {column.name}",
                        f"{table_name} where {column.name} is"
                    ],
                    required_tables=[table_name],
                    required_columns=[column.name],
                    confidence=0.7
                ))

            elif column.semantic_type == ColumnType.NUMERIC:
                # Range and comparison filters
                patterns.append(QueryPattern(
                    pattern_name=f"compare_{table_name}_{column.name}",
                    template=f"SELECT * FROM {table_name} WHERE {column.name} {{operator}} {{value}}",
                    example_queries=[
                        f"{table_name} with {column.name} greater than",
                        f"{table_name} where {column.name} is less than",
                        f"Show {table_name} with {column.name} above"
                    ],
                    required_tables=[table_name],
                    required_columns=[column.name],
                    confidence=0.7
                ))

        return patterns

    def _generate_relationship_patterns(self, schema_analysis: SchemaAnalysis) -> List[QueryPattern]:
        """Generate patterns for table relationships"""
        patterns = []

        # Build table lookup
        tables_by_name = {table.name: table for table in schema_analysis.tables}

        for relationship in schema_analysis.relationships:
            from_table = relationship.get('from_table')
            to_table = relationship.get('to_table')
            from_column = relationship.get('from_column')
            to_column = relationship.get('to_column', 'id')

            if from_table in tables_by_name and to_table in tables_by_name:
                from_table_obj = tables_by_name[from_table]
                to_table_obj = tables_by_name[to_table]

                # Basic join pattern
                patterns.append(QueryPattern(
                    pattern_name=f"join_{from_table}_with_{to_table}",
                    template=f"SELECT f.*, t.* FROM {from_table} f JOIN {to_table} t ON f.{from_column} = t.{to_column}",
                    example_queries=[
                        f"Show {from_table} with their {to_table}",
                        f"{from_table} and their {to_table}",
                        f"List {from_table} including {to_table}"
                    ],
                    required_tables=[from_table, to_table],
                    required_columns=[from_column, to_column],
                    confidence=0.8
                ))

                # Selective join pattern
                name_column = self._find_name_column(to_table_obj)
                if name_column:
                    patterns.append(QueryPattern(
                        pattern_name=f"join_{from_table}_with_{to_table}_names",
                        template=f"SELECT f.*, t.{name_column.name} as {to_table}_name FROM {from_table} f JOIN {to_table} t ON f.{from_column} = t.{to_column}",
                        example_queries=[
                            f"Show {from_table} with {to_table} names",
                            f"{from_table} including {to_table} name",
                            f"List {from_table} and {to_table} details"
                        ],
                        required_tables=[from_table, to_table],
                        required_columns=[from_column, to_column, name_column.name],
                        confidence=0.8
                    ))

        return patterns

    def _generate_aggregation_patterns(self, schema_analysis: SchemaAnalysis) -> List[QueryPattern]:
        """Generate aggregation patterns"""
        patterns = []

        # Build table lookup
        tables_by_name = {table.name: table for table in schema_analysis.tables}

        # Find tables with amount columns that can be aggregated by categories
        for table in schema_analysis.tables:
            if table.table_type != 'entity':
                continue

            amount_columns = [col for col in table.columns if col.semantic_type == ColumnType.AMOUNT]
            fk_columns = [col for col in table.columns if col.is_foreign_key]

            for amount_col in amount_columns:
                for fk_col in fk_columns:
                    # Find the related table
                    related_table_name = fk_col.foreign_table
                    if related_table_name and related_table_name in tables_by_name:
                        related_table = tables_by_name[related_table_name]
                        category_column = self._find_name_column(related_table)

                        if category_column:
                            # Generate aggregation pattern
                            for agg_name, agg_func in [('average', 'AVG'), ('total', 'SUM'), ('count', 'COUNT')]:
                                patterns.append(QueryPattern(
                                    pattern_name=f"{agg_name}_{amount_col.name}_by_{related_table_name}",
                                    template=f"SELECT c.{category_column.name}, {agg_func}(p.{amount_col.name}) as {agg_name}_{amount_col.name} FROM {table.name} p JOIN {related_table_name} c ON p.{fk_col.name} = c.id GROUP BY c.id, c.{category_column.name}",
                                    example_queries=[
                                        f"Show {agg_name} {amount_col.name} by {related_table_name}",
                                        f"{agg_name.capitalize()} {amount_col.name} per {related_table_name}",
                                        f"Group {amount_col.name} by {related_table_name}"
                                    ],
                                    required_tables=[table.name, related_table_name],
                                    required_columns=[amount_col.name, fk_col.name, category_column.name],
                                    confidence=0.9
                                ))

        return patterns

    def _generate_few_shot_examples(self, schema_analysis: SchemaAnalysis, patterns: List[QueryPattern]) -> List[FewShotExample]:
        """Generate few-shot examples from patterns"""
        examples = []

        # Convert high-confidence patterns to few-shot examples
        for pattern in patterns:
            if pattern.confidence >= 0.8 and pattern.example_queries:
                # Use the first example query as the question
                question = pattern.example_queries[0]
                sql = pattern.template

                # Try to make SQL more concrete by filling in some placeholders
                sql = self._concretize_sql_template(sql, schema_analysis)

                examples.append(FewShotExample(
                    question=question,
                    sql=sql,
                    explanation=f"Generated from {pattern.pattern_name} pattern",
                    pattern_type=pattern.pattern_name.split('_')[0],
                    confidence=pattern.confidence
                ))

        # Add some hand-crafted examples for common scenarios
        examples.extend(self._generate_domain_specific_examples(schema_analysis))

        # Sort by confidence and take top examples
        examples.sort(key=lambda x: x.confidence, reverse=True)
        return examples[:20]  # Limit to top 20 examples

    def _concretize_sql_template(self, sql_template: str, schema_analysis: SchemaAnalysis) -> str:
        """Make SQL template more concrete by filling common placeholders"""
        sql = sql_template

        # Replace common placeholders with reasonable defaults
        replacements = {
            '{limit}': '10',
            '{n}': '5',
            '{operator}': '>',
            '{value}': '100',
            '{min_val}': '0',
            '{max_val}': '1000',
            '{date_operator}': '>=',
            '{date_value}': "'2024-01-01'"
        }

        for placeholder, default_value in replacements.items():
            sql = sql.replace(placeholder, default_value)

        return sql

    def _generate_domain_specific_examples(self, schema_analysis: SchemaAnalysis) -> List[FewShotExample]:
        """Generate domain-specific examples based on detected domain"""
        examples = []

        # Detect domain from table names and vocabulary
        domain = self._detect_domain(schema_analysis)

        if domain == 'ecommerce':
            examples.extend(self._generate_ecommerce_examples(schema_analysis))
        elif domain == 'crm':
            examples.extend(self._generate_crm_examples(schema_analysis))
        elif domain == 'hr':
            examples.extend(self._generate_hr_examples(schema_analysis))
        # Add more domains as needed

        return examples

    def _detect_domain(self, schema_analysis: SchemaAnalysis) -> str:
        """Detect the domain based on table names and vocabulary"""
        table_names = [table.name.lower() for table in schema_analysis.tables]

        # Domain keywords
        domain_keywords = {
            'ecommerce': ['product', 'order', 'customer', 'cart', 'payment', 'category', 'inventory'],
            'crm': ['lead', 'contact', 'account', 'opportunity', 'deal', 'campaign'],
            'hr': ['employee', 'department', 'position', 'salary', 'benefit'],
            'finance': ['transaction', 'account', 'balance', 'investment'],
            'healthcare': ['patient', 'doctor', 'appointment', 'treatment'],
            'education': ['student', 'course', 'grade', 'enrollment', 'teacher']
        }

        domain_scores = {}
        for domain, keywords in domain_keywords.items():
            score = sum(1 for keyword in keywords if any(keyword in table_name for table_name in table_names))
            domain_scores[domain] = score

        # Return domain with highest score
        if domain_scores:
            return max(domain_scores, key=domain_scores.get)
        return 'general'

    def _generate_ecommerce_examples(self, schema_analysis: SchemaAnalysis) -> List[FewShotExample]:
        """Generate e-commerce specific examples"""
        examples = []

        # Find relevant tables
        tables_by_name = {table.name.lower(): table for table in schema_analysis.tables}

        if 'products' in tables_by_name and 'categories' in tables_by_name:
            examples.append(FewShotExample(
                question="Show average price by category",
                sql="SELECT c.name as category, AVG(p.price) as average_price FROM products p JOIN categories c ON p.category_id = c.id GROUP BY c.id, c.name",
                explanation="Join products with categories and calculate average price per category",
                pattern_type="aggregation",
                confidence=0.95
            ))

        if 'products' in tables_by_name:
            products_table = tables_by_name['products']
            stock_column = self._find_column_by_type(products_table, ColumnType.NUMERIC, ['stock', 'quantity'])
            if stock_column:
                examples.append(FewShotExample(
                    question=f"Show products with {stock_column.name} below 10",
                    sql=f"SELECT * FROM products WHERE {stock_column.name} < 10",
                    explanation="Filter products with low stock levels",
                    pattern_type="filter",
                    confidence=0.9
                ))

        return examples

    def _generate_column_mappings(self, schema_analysis: SchemaAnalysis) -> Dict[str, str]:
        """Generate natural language to column mappings"""
        mappings = {}

        for table in schema_analysis.tables:
            table_name = table.name

            # Map table name variations
            mappings[table_name] = table_name
            mappings[table_name.rstrip('s')] = table_name  # Singular form
            if not table_name.endswith('s'):
                mappings[table_name + 's'] = table_name  # Plural form

            for column in table.columns:
                col_name = column.name
                full_ref = f"{table_name}.{col_name}"

                # Direct column mappings
                mappings[col_name] = full_ref

                # Semantic mappings
                if column.semantic_type == ColumnType.NAME:
                    mappings[f"{table_name} name"] = full_ref
                    mappings[f"name of {table_name}"] = full_ref

                elif column.semantic_type == ColumnType.AMOUNT:
                    # Map various amount terms
                    amount_terms = ['price', 'cost', 'amount', 'total', 'value']
                    for term in amount_terms:
                        if term in col_name.lower():
                            mappings[term] = full_ref
                            mappings[f"{table_name} {term}"] = full_ref

                elif column.semantic_type == ColumnType.DATE:
                    mappings['date'] = full_ref
                    if 'created' in col_name.lower():
                        mappings['created date'] = full_ref
                        mappings['creation date'] = full_ref

                # Extract terms from column name
                if column.common_terms:
                    for term in column.common_terms:
                        if len(term) > 2:  # Skip very short terms
                            mappings[term] = full_ref

        return mappings

    def _format_relationships(self, schema_analysis: SchemaAnalysis) -> List[Dict[str, Any]]:
        """Format relationships for template use"""
        formatted = []

        for rel in schema_analysis.relationships:
            formatted.append({
                'from_table': rel.get('from_table'),
                'to_table': rel.get('to_table'),
                'from_column': rel.get('from_column'),
                'to_column': rel.get('to_column', 'id'),
                'relationship_type': rel.get('type', 'foreign_key'),
                'confidence': rel.get('confidence', 1.0),
                'join_condition': f"{rel.get('from_table')}.{rel.get('from_column')} = {rel.get('to_table')}.{rel.get('to_column', 'id')}"
            })

        return formatted

    def _generate_phrase_mappings(self, schema_analysis: SchemaAnalysis) -> Dict[str, str]:
        """Generate common phrase to SQL mappings"""
        phrases = {}

        # Basic phrase mappings
        phrases.update({
            'show all': 'SELECT * FROM',
            'list all': 'SELECT * FROM',
            'count all': 'SELECT COUNT(*) FROM',
            'how many': 'SELECT COUNT(*) FROM',
            'average': 'AVG',
            'total': 'SUM',
            'maximum': 'MAX',
            'minimum': 'MIN',
            'highest': 'ORDER BY {column} DESC',
            'lowest': 'ORDER BY {column} ASC',
            'top': 'ORDER BY {column} DESC LIMIT',
            'bottom': 'ORDER BY {column} ASC LIMIT'
        })

        # Domain-specific phrases based on schema
        domain = self._detect_domain(schema_analysis)
        if domain == 'ecommerce':
            phrases.update({
                'most expensive': 'ORDER BY price DESC',
                'cheapest': 'ORDER BY price ASC',
                'out of stock': 'WHERE stock_quantity = 0',
                'low stock': 'WHERE stock_quantity < 10'
            })

        return phrases

    def _find_name_column(self, table: TableAnalysis) -> Optional[ColumnAnalysis]:
        """Find the name column in a table"""
        for column in table.columns:
            if column.semantic_type == ColumnType.NAME:
                return column
        return None

    def _find_column_by_type(self, table: TableAnalysis, col_type: ColumnType, keywords: List[str] = None) -> Optional[ColumnAnalysis]:
        """Find a column of specific type, optionally matching keywords"""
        for column in table.columns:
            if column.semantic_type == col_type:
                if keywords:
                    if any(keyword in column.name.lower() for keyword in keywords):
                        return column
                else:
                    return column
        return None

    def export_templates_as_code(self, templates: DynamicQueryTemplates) -> str:
        """Export templates as Python code for integration"""
        code_lines = [
            f'"""Auto-generated query templates for {templates.schema_name}"""',
            '',
            'from typing import Dict, List, Any',
            '',
            f'SCHEMA_NAME = "{templates.schema_name}"',
            '',
            '# Few-shot examples',
            'FEW_SHOT_EXAMPLES = ['
        ]

        for example in templates.few_shot_examples[:10]:  # Limit to top 10
            code_lines.append(f'    {{')
            code_lines.append(f'        "question": "{example.question}",')
            code_lines.append(f'        "sql": """{example.sql}""",')
            code_lines.append(f'        "explanation": "{example.explanation}"')
            code_lines.append(f'    }},')

        code_lines.extend([
            ']',
            '',
            '# Column mappings',
            f'COLUMN_MAPPINGS = {repr(templates.column_mappings)}',
            '',
            '# Common phrases',
            f'COMMON_PHRASES = {repr(templates.common_phrases)}',
            '',
            '# Table relationships',
            f'TABLE_RELATIONSHIPS = {repr(templates.table_relationships)}'
        ])

        return '\n'.join(code_lines)