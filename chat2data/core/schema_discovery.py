"""Schema Discovery Engine for Chat2Data Framework

Automatically analyzes any database schema to understand structure, relationships,
and patterns for generating accurate SQL queries from natural language.
"""

import logging
import re
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict, Counter

logger = logging.getLogger(__name__)


class ColumnType(Enum):
    """Semantic column types for better understanding"""
    IDENTIFIER = "identifier"  # Primary keys, IDs
    NAME = "name"  # Names, titles, descriptions
    AMOUNT = "amount"  # Prices, costs, quantities, amounts
    DATE = "date"  # Dates, timestamps
    STATUS = "status"  # Status flags, categories
    FOREIGN_KEY = "foreign_key"  # References to other tables
    BOOLEAN = "boolean"  # True/false flags
    TEXT = "text"  # Long text content
    NUMERIC = "numeric"  # Numbers without semantic meaning
    OTHER = "other"  # Unclassified


@dataclass
class ColumnAnalysis:
    """Analysis results for a single column"""
    name: str
    sql_type: str
    semantic_type: ColumnType
    is_primary_key: bool = False
    is_foreign_key: bool = False
    foreign_table: Optional[str] = None
    is_nullable: bool = True
    sample_values: List[Any] = None
    common_terms: List[str] = None


@dataclass
class TableAnalysis:
    """Analysis results for a single table"""
    name: str
    columns: List[ColumnAnalysis]
    row_count: int = 0
    relationships: List[Dict[str, Any]] = None
    domain_terms: List[str] = None
    table_type: str = "entity"  # entity, junction, lookup


@dataclass
class SchemaAnalysis:
    """Complete schema analysis results"""
    database_name: str
    tables: List[TableAnalysis]
    relationships: List[Dict[str, Any]]
    domain_vocabulary: Dict[str, str]
    common_patterns: List[str]
    suggested_queries: List[str]


class SchemaDiscoveryEngine:
    """Discovers and analyzes database schemas for automatic adaptation"""

    def __init__(self, database_provider):
        """Initialize with a database provider"""
        self.database_provider = database_provider
        self.schema_cache = {}

        # Patterns for identifying column semantics
        self.column_patterns = {
            ColumnType.IDENTIFIER: [
                r'.*id$', r'^id$', r'.*_id$', r'.*key$', r'.*pk$'
            ],
            ColumnType.NAME: [
                r'.*name$', r'.*title$', r'.*label$', r'.*description$',
                r'.*desc$', r'^name$', r'^title$'
            ],
            ColumnType.AMOUNT: [
                r'.*price$', r'.*cost$', r'.*amount$', r'.*total$',
                r'.*quantity$', r'.*qty$', r'.*value$', r'.*fee$',
                r'.*rate$', r'.*salary$', r'.*income$'
            ],
            ColumnType.DATE: [
                r'.*date$', r'.*time$', r'.*created$', r'.*updated$',
                r'.*modified$', r'.*timestamp$', r'^date$', r'^time$'
            ],
            ColumnType.STATUS: [
                r'.*status$', r'.*state$', r'.*type$', r'.*category$',
                r'.*level$', r'.*priority$', r'.*stage$'
            ],
            ColumnType.BOOLEAN: [
                r'.*active$', r'.*enabled$', r'.*visible$', r'.*deleted$',
                r'^is_.*', r'^has_.*', r'^can_.*'
            ]
        }

        # Common domain vocabularies
        self.domain_terms = {
            'ecommerce': ['product', 'customer', 'order', 'cart', 'payment', 'shipping'],
            'crm': ['lead', 'contact', 'account', 'opportunity', 'deal', 'campaign'],
            'hr': ['employee', 'department', 'position', 'salary', 'benefit', 'performance'],
            'finance': ['transaction', 'account', 'balance', 'investment', 'portfolio'],
            'healthcare': ['patient', 'doctor', 'appointment', 'treatment', 'diagnosis'],
            'education': ['student', 'course', 'grade', 'enrollment', 'teacher', 'class']
        }

    def analyze_database_schema(self) -> SchemaAnalysis:
        """Analyze the complete database schema"""
        try:
            logger.info("Starting comprehensive database schema analysis")

            # Get raw schema information
            schema_info = self.database_provider.get_schema()

            if not schema_info:
                raise ValueError("No schema information available from database")

            # Analyze each table
            analyzed_tables = []
            for table_info in schema_info:
                table_analysis = self.analyze_table(table_info)
                analyzed_tables.append(table_analysis)

            # Detect relationships between tables
            relationships = self.detect_table_relationships(analyzed_tables)

            # Generate domain vocabulary
            domain_vocab = self.generate_domain_vocabulary(analyzed_tables)

            # Identify common patterns
            patterns = self.identify_common_patterns(analyzed_tables)

            # Generate suggested queries
            suggested_queries = self.generate_suggested_queries(analyzed_tables, relationships)

            analysis = SchemaAnalysis(
                database_name=getattr(self.database_provider, 'database_name', 'unknown'),
                tables=analyzed_tables,
                relationships=relationships,
                domain_vocabulary=domain_vocab,
                common_patterns=patterns,
                suggested_queries=suggested_queries
            )

            logger.info(f"Schema analysis complete: {len(analyzed_tables)} tables, "
                       f"{len(relationships)} relationships, {len(domain_vocab)} vocabulary terms")

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing database schema: {e}")
            raise

    def analyze_table(self, table_info) -> TableAnalysis:
        """Analyze a single table and its columns"""
        table_name = table_info.name
        logger.debug(f"Analyzing table: {table_name}")

        # Analyze columns
        analyzed_columns = []
        for column in table_info.columns:
            column_analysis = self.analyze_column(column, table_name)
            analyzed_columns.append(column_analysis)

        # Determine table type
        table_type = self.determine_table_type(table_name, analyzed_columns)

        # Extract domain terms from table name
        domain_terms = self.extract_domain_terms(table_name)

        return TableAnalysis(
            name=table_name,
            columns=analyzed_columns,
            row_count=getattr(table_info, 'row_count', 0),
            domain_terms=domain_terms,
            table_type=table_type
        )

    def analyze_column(self, column_info, table_name: str) -> ColumnAnalysis:
        """Analyze a single column to determine its semantic type"""
        if isinstance(column_info, dict):
            col_name = column_info.get('name', '')
            sql_type = column_info.get('type', '')
            is_pk = column_info.get('primary_key', False)
            is_fk = column_info.get('foreign_key') is not None
            fk_table = column_info.get('foreign_key', '').split('.')[0] if is_fk else None
            nullable = column_info.get('nullable', True)
        else:
            col_name = str(column_info)
            sql_type = 'unknown'
            is_pk = False
            is_fk = False
            fk_table = None
            nullable = True

        # Determine semantic type
        semantic_type = self.infer_column_semantics(col_name, sql_type, is_pk, is_fk)

        # Extract common terms from column name
        common_terms = self.extract_column_terms(col_name)

        return ColumnAnalysis(
            name=col_name,
            sql_type=sql_type,
            semantic_type=semantic_type,
            is_primary_key=is_pk,
            is_foreign_key=is_fk,
            foreign_table=fk_table,
            is_nullable=nullable,
            common_terms=common_terms
        )

    def infer_column_semantics(self, col_name: str, sql_type: str, is_pk: bool, is_fk: bool) -> ColumnType:
        """Infer the semantic type of a column based on name and type"""
        col_lower = col_name.lower()
        type_lower = sql_type.lower()

        # Primary keys are always identifiers
        if is_pk:
            return ColumnType.IDENTIFIER

        # Foreign keys are foreign key type
        if is_fk:
            return ColumnType.FOREIGN_KEY

        # Check patterns for semantic types
        for semantic_type, patterns in self.column_patterns.items():
            for pattern in patterns:
                if re.match(pattern, col_lower):
                    return semantic_type

        # Fallback based on SQL type
        if 'bool' in type_lower:
            return ColumnType.BOOLEAN
        elif 'date' in type_lower or 'time' in type_lower:
            return ColumnType.DATE
        elif 'text' in type_lower or 'char' in type_lower and 'varchar(255)' not in type_lower:
            return ColumnType.TEXT
        elif any(num_type in type_lower for num_type in ['int', 'float', 'decimal', 'numeric']):
            return ColumnType.NUMERIC

        return ColumnType.OTHER

    def detect_table_relationships(self, tables: List[TableAnalysis]) -> List[Dict[str, Any]]:
        """Detect relationships between tables"""
        relationships = []

        # Build lookup for table names
        table_names = {table.name.lower() for table in tables}

        for table in tables:
            for column in table.columns:
                if column.is_foreign_key and column.foreign_table:
                    # Explicit foreign key relationship
                    relationships.append({
                        'type': 'foreign_key',
                        'from_table': table.name,
                        'from_column': column.name,
                        'to_table': column.foreign_table,
                        'to_column': 'id',  # Assume ID column
                        'confidence': 1.0
                    })
                elif column.name.endswith('_id') and not column.is_primary_key:
                    # Inferred relationship based on naming convention
                    potential_table = column.name[:-3]  # Remove '_id'

                    # Try different pluralization patterns
                    candidates = [
                        potential_table,
                        potential_table + 's',
                        potential_table[:-1] if potential_table.endswith('s') else potential_table,
                    ]

                    for candidate in candidates:
                        if candidate.lower() in table_names:
                            relationships.append({
                                'type': 'inferred',
                                'from_table': table.name,
                                'from_column': column.name,
                                'to_table': candidate,
                                'to_column': 'id',
                                'confidence': 0.8
                            })
                            break

        return relationships

    def determine_table_type(self, table_name: str, columns: List[ColumnAnalysis]) -> str:
        """Determine the type of table (entity, junction, lookup)"""
        fk_count = sum(1 for col in columns if col.is_foreign_key)
        total_cols = len(columns)

        # Junction table: mostly foreign keys
        if fk_count >= 2 and fk_count / total_cols > 0.5:
            return 'junction'

        # Lookup table: small, simple structure
        if total_cols <= 4 and any(col.semantic_type == ColumnType.NAME for col in columns):
            return 'lookup'

        return 'entity'

    def extract_domain_terms(self, name: str) -> List[str]:
        """Extract domain-specific terms from table/column names"""
        # Split camelCase and snake_case
        terms = re.split(r'[_\s]+|(?=[A-Z])', name.lower())
        terms = [term for term in terms if term and len(term) > 1]

        # Remove common SQL words
        sql_words = {'id', 'key', 'pk', 'fk', 'ref', 'idx', 'tmp', 'temp'}
        terms = [term for term in terms if term not in sql_words]

        return terms

    def extract_column_terms(self, col_name: str) -> List[str]:
        """Extract meaningful terms from column names"""
        return self.extract_domain_terms(col_name)

    def generate_domain_vocabulary(self, tables: List[TableAnalysis]) -> Dict[str, str]:
        """Generate domain vocabulary mapping common terms to database columns"""
        vocabulary = {}

        # Collect all terms from tables and columns
        all_terms = []
        for table in tables:
            if table.domain_terms:
                all_terms.extend(table.domain_terms)
            for column in table.columns:
                if column.common_terms:
                    all_terms.extend(column.common_terms)

        # Count term frequency
        term_counts = Counter(all_terms)

        # Map common terms to their most likely columns
        for table in tables:
            for column in table.columns:
                if column.semantic_type == ColumnType.NAME:
                    # Map table name to this column
                    table_singular = table.name.rstrip('s')
                    vocabulary[table_singular] = f"{table.name}.{column.name}"
                    vocabulary[table.name] = f"{table.name}.{column.name}"

                elif column.semantic_type == ColumnType.AMOUNT:
                    # Map amount-related terms
                    for term in ['price', 'cost', 'amount', 'total']:
                        if term in column.name.lower():
                            vocabulary[term] = f"{table.name}.{column.name}"

                elif column.semantic_type == ColumnType.DATE:
                    # Map date-related terms
                    vocabulary['date'] = f"{table.name}.{column.name}"
                    if 'created' in column.name.lower():
                        vocabulary['created'] = f"{table.name}.{column.name}"

        return vocabulary

    def identify_common_patterns(self, tables: List[TableAnalysis]) -> List[str]:
        """Identify common query patterns based on schema structure"""
        patterns = []

        # Count table types
        entity_tables = [t for t in tables if t.table_type == 'entity']
        lookup_tables = [t for t in tables if t.table_type == 'lookup']

        if len(entity_tables) >= 2:
            patterns.append("multi_entity_queries")

        if lookup_tables:
            patterns.append("category_grouping")

        # Check for amount columns (aggregation patterns)
        has_amounts = any(
            any(col.semantic_type == ColumnType.AMOUNT for col in table.columns)
            for table in tables
        )
        if has_amounts:
            patterns.append("aggregation_queries")

        # Check for date columns (time-based queries)
        has_dates = any(
            any(col.semantic_type == ColumnType.DATE for col in table.columns)
            for table in tables
        )
        if has_dates:
            patterns.append("temporal_queries")

        return patterns

    def generate_suggested_queries(self, tables: List[TableAnalysis],
                                 relationships: List[Dict[str, Any]]) -> List[str]:
        """Generate suggested natural language queries based on schema"""
        queries = []

        # Basic queries for each entity table
        for table in tables:
            if table.table_type == 'entity':
                queries.append(f"Show all {table.name}")
                queries.append(f"Count all {table.name}")

                # Amount-based queries
                amount_cols = [col for col in table.columns if col.semantic_type == ColumnType.AMOUNT]
                if amount_cols:
                    queries.append(f"Show total {amount_cols[0].name} from {table.name}")

        # Relationship-based queries
        for rel in relationships:
            if rel['confidence'] > 0.8:
                queries.append(f"Show {rel['from_table']} with their {rel['to_table']}")

        # Category-based queries (if lookup tables exist)
        lookup_tables = [t for t in tables if t.table_type == 'lookup']
        entity_tables = [t for t in tables if t.table_type == 'entity']

        for lookup in lookup_tables:
            for entity in entity_tables:
                # Check if there's a relationship
                related = any(
                    rel['from_table'] == entity.name and rel['to_table'] == lookup.name
                    for rel in relationships
                )
                if related:
                    amount_cols = [col for col in entity.columns if col.semantic_type == ColumnType.AMOUNT]
                    if amount_cols:
                        queries.append(f"Show average {amount_cols[0].name} by {lookup.name}")

        return queries[:10]  # Limit to top 10 suggestions