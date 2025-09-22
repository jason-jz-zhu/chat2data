"""Domain Adapter for Chat2Data Framework

Bridges schema analysis and dynamic templates with existing Chat2Data components,
enabling seamless adaptation to any database schema while preserving accuracy mechanisms.
"""

import logging
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict

from .schema_discovery import SchemaDiscoveryEngine, SchemaAnalysis
from .dynamic_template_generator import DynamicTemplateGenerator, DynamicQueryTemplates
from .query_templates import QueryTemplates

logger = logging.getLogger(__name__)


@dataclass
class DomainConfiguration:
    """Configuration for a specific domain/database"""
    schema_name: str
    database_path: str
    schema_analysis: SchemaAnalysis
    dynamic_templates: DynamicQueryTemplates
    confidence_threshold: float = 0.7
    use_smart_pipeline: bool = True


class DomainAdapter:
    """Adapts Chat2Data to work with any database schema automatically"""

    def __init__(self, database_provider):
        """Initialize domain adapter with database provider"""
        self.database_provider = database_provider
        self.schema_engine = SchemaDiscoveryEngine(database_provider)
        self.template_generator = DynamicTemplateGenerator()

        # Current domain configuration
        self.current_domain: Optional[DomainConfiguration] = None
        self.adapted_templates: Optional[QueryTemplates] = None

        # Caching
        self._analysis_cache = {}
        self._template_cache = {}

    async def analyze_and_adapt(self) -> DomainConfiguration:
        """Analyze the database and adapt Chat2Data components"""
        try:
            logger.info("Starting domain analysis and adaptation...")

            # Step 1: Analyze database schema
            try:
                schema_analysis = await self._analyze_schema()
            except Exception as e:
                logger.error(f"Schema analysis failed: {e}")
                # Create minimal fallback schema analysis
                schema_analysis = self._create_fallback_schema_analysis()

            # Step 2: Generate dynamic templates
            try:
                dynamic_templates = await self._generate_templates(schema_analysis)
            except Exception as e:
                logger.error(f"Template generation failed: {e}")
                # Create minimal fallback templates
                dynamic_templates = self._create_fallback_templates(schema_analysis)

            # Step 3: Create domain configuration
            domain_config = DomainConfiguration(
                schema_name=schema_analysis.database_name,
                database_path=getattr(self.database_provider, 'database_path', 'unknown'),
                schema_analysis=schema_analysis,
                dynamic_templates=dynamic_templates,
                confidence_threshold=0.5,  # Lower threshold for fallback mode
                use_smart_pipeline=False   # Disable smart features in fallback mode
            )

            # Step 4: Adapt existing components
            try:
                await self._adapt_components(domain_config)
            except Exception as e:
                logger.error(f"Component adaptation failed: {e}")
                # Create basic adapted templates without domain adapter dependency
                self.adapted_templates = self._create_fallback_adapted_templates()

            # Cache the configuration
            self.current_domain = domain_config

            logger.info(f"Domain adaptation complete for: {schema_analysis.database_name}")
            return domain_config

        except Exception as e:
            logger.error(f"Critical error during domain adaptation: {e}")
            # Create minimal fallback configuration to keep system operational
            fallback_config = self._create_minimal_fallback_configuration()
            self.current_domain = fallback_config
            return fallback_config

    async def _analyze_schema(self) -> SchemaAnalysis:
        """Analyze database schema with caching"""
        cache_key = getattr(self.database_provider, 'database_path', 'default')

        if cache_key in self._analysis_cache:
            logger.debug("Using cached schema analysis")
            return self._analysis_cache[cache_key]

        logger.info("Performing fresh schema analysis...")
        analysis = self.schema_engine.analyze_database_schema()

        # Cache the analysis
        self._analysis_cache[cache_key] = analysis
        return analysis

    async def _generate_templates(self, schema_analysis: SchemaAnalysis) -> DynamicQueryTemplates:
        """Generate dynamic templates with caching"""
        cache_key = schema_analysis.database_name

        if cache_key in self._template_cache:
            logger.debug("Using cached dynamic templates")
            return self._template_cache[cache_key]

        logger.info("Generating dynamic templates...")
        templates = self.template_generator.generate_templates(schema_analysis)

        # Cache the templates
        self._template_cache[cache_key] = templates
        return templates

    async def _adapt_components(self, domain_config: DomainConfiguration):
        """Adapt existing Chat2Data components to the new domain"""
        # Create adapted query templates
        self.adapted_templates = self._create_adapted_query_templates(domain_config)

        # Update accuracy mechanisms
        await self._update_accuracy_mechanisms(domain_config)

    def _create_adapted_query_templates(self, domain_config: DomainConfiguration) -> QueryTemplates:
        """Create adapted query templates that merge dynamic and static templates"""

        # Start with existing QueryTemplates structure and pass domain adapter
        adapted = QueryTemplates(domain_adapter=self)

        # Prepare dynamic few-shot examples
        dynamic_examples = []

        # Add high-confidence dynamic examples first
        for example in domain_config.dynamic_templates.few_shot_examples:
            if example.confidence >= domain_config.confidence_threshold:
                dynamic_examples.append({
                    'question': example.question,
                    'sql': example.sql,
                    'explanation': example.explanation
                })

        # Prepare column mappings (merge with fallback)
        fallback_mappings = adapted._get_fallback_column_mappings()
        dynamic_column_mappings = {
            **fallback_mappings,  # Keep fallback mappings
            **domain_config.dynamic_templates.column_mappings  # Override with dynamic
        }

        # Prepare table relationships
        dynamic_relationships = self._format_relationships_for_query_templates(
            domain_config.dynamic_templates.table_relationships
        )

        # Use the set_dynamic_content method to properly set the content
        adapted.set_dynamic_content(
            examples=dynamic_examples,
            column_mappings=dynamic_column_mappings,
            relationships=dynamic_relationships
        )

        logger.info(f"Created adapted templates with {len(dynamic_examples)} examples")
        return adapted

    def _format_relationships_for_templates(self, relationships: List[Dict[str, Any]]) -> List[str]:
        """Format relationships for QueryTemplates format"""
        formatted = []

        for rel in relationships:
            rel_str = f"{rel['from_table']}.{rel['from_column']} → {rel['to_table']}.{rel['to_column']}"
            formatted.append(rel_str)

        return formatted

    def _format_relationships_for_query_templates(self, relationships: List[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, str]]:
        """Format relationships for QueryTemplates TABLE_RELATIONSHIPS format"""
        formatted = {}

        for rel in relationships:
            key = (rel['from_table'], rel['to_table'])
            formatted[key] = {
                "join_condition": rel.get('join_condition', f"{rel['from_table']}.{rel['from_column']} = {rel['to_table']}.{rel['to_column']}"),
                "foreign_key": rel['from_column'],
                "primary_key": rel['to_column']
            }

        return formatted

    def _create_dynamic_query_patterns(self, domain_config: DomainConfiguration) -> Dict[str, List[str]]:
        """Create query patterns from dynamic analysis"""
        patterns = {}

        # Extract patterns from schema analysis
        for pattern_name in domain_config.schema_analysis.common_patterns:
            if pattern_name == 'aggregation_queries':
                patterns['aggregation'] = [
                    'average {column} by {category}',
                    'sum {column} by {category}',
                    'total {column} per {category}',
                    'count by {category}'
                ]
            elif pattern_name == 'temporal_queries':
                patterns['temporal'] = [
                    'recent {table}',
                    'last {number} {table}',
                    '{table} since {date}',
                    '{table} between {date1} and {date2}'
                ]
            elif pattern_name == 'multi_entity_queries':
                patterns['multi_entity'] = [
                    '{table1} with their {table2}',
                    '{table1} and {table2}',
                    'join {table1} with {table2}'
                ]

        # Add domain-specific patterns
        domain = self._detect_domain_from_analysis(domain_config.schema_analysis)
        if domain == 'ecommerce':
            patterns['ecommerce'] = [
                'top products by price',
                'products by category',
                'low stock products',
                'orders with customers'
            ]

        return patterns

    def _detect_domain_from_analysis(self, schema_analysis: SchemaAnalysis) -> str:
        """Detect domain from schema analysis"""
        table_names = [table.name.lower() for table in schema_analysis.tables]

        # Use domain vocabulary from schema analysis
        for domain, terms in schema_analysis.domain_vocabulary.items():
            if any(term.lower() in ' '.join(table_names) for term in terms if isinstance(terms, list)):
                return domain

        # Fallback detection
        if any(name in table_names for name in ['product', 'order', 'customer']):
            return 'ecommerce'
        elif any(name in table_names for name in ['employee', 'department']):
            return 'hr'
        elif any(name in table_names for name in ['patient', 'doctor']):
            return 'healthcare'

        return 'general'

    async def _update_accuracy_mechanisms(self, domain_config: DomainConfiguration):
        """Update all accuracy improvement mechanisms"""

        # Update vector store with domain-specific context
        await self._update_vector_store_context(domain_config)

        # Generate system prompts for LLM providers
        self._generate_domain_specific_prompts(domain_config)

    async def _update_vector_store_context(self, domain_config: DomainConfiguration):
        """Update vector store with domain-specific schema context"""
        try:
            # Prepare schema context for vector storage
            schema_contexts = []

            for table in domain_config.schema_analysis.tables:
                context = {
                    'type': 'table_schema',
                    'name': table.name,
                    'domain': domain_config.schema_name,
                    'description': f"Table {table.name} with {len(table.columns)} columns",
                    'columns': [col.name for col in table.columns],
                    'semantic_types': {col.name: col.semantic_type.value for col in table.columns},
                    'table_type': table.table_type
                }
                schema_contexts.append(context)

            # Store relationships
            for rel in domain_config.dynamic_templates.table_relationships:
                context = {
                    'type': 'relationship',
                    'description': f"{rel['from_table']} connects to {rel['to_table']}",
                    'relationship': rel,
                    'domain': domain_config.schema_name
                }
                schema_contexts.append(context)

            # Store few-shot examples
            for example in domain_config.dynamic_templates.few_shot_examples:
                context = {
                    'type': 'query_example',
                    'question': example.question,
                    'sql': example.sql,
                    'pattern_type': example.pattern_type,
                    'domain': domain_config.schema_name,
                    'confidence': example.confidence
                }
                schema_contexts.append(context)

            logger.info(f"Prepared {len(schema_contexts)} context items for vector store")

        except Exception as e:
            logger.warning(f"Failed to update vector store context: {e}")

    def _generate_domain_specific_prompts(self, domain_config: DomainConfiguration):
        """Generate domain-specific system prompts"""

        # Build comprehensive database structure description
        db_structure = self._build_database_structure_description(domain_config.schema_analysis)

        # Build relationship description
        relationships = self._build_relationship_description(domain_config.dynamic_templates.table_relationships)

        # Build examples section
        examples = self._build_examples_section(domain_config.dynamic_templates.few_shot_examples[:5])

        # Create system prompt
        domain_config.system_prompt = f"""You are an expert SQL query generator for a {domain_config.schema_name} database system.

## DATABASE STRUCTURE:
{db_structure}

## TABLE RELATIONSHIPS:
{relationships}

## QUERY EXAMPLES:
{examples}

## STRICT RULES:
1. ONLY generate SELECT queries
2. Use EXACT table and column names from the schema above
3. When joining tables, use the relationships listed above
4. Always use proper JOIN conditions
5. Return ONLY the SQL query, no explanations

## IMPORTANT:
- Follow the example patterns shown above
- Never use non-existent columns or tables
- Always use proper JOIN conditions from the relationships above"""

        logger.info("Generated domain-specific system prompt")

    def _build_database_structure_description(self, schema_analysis: SchemaAnalysis) -> str:
        """Build comprehensive database structure description"""
        lines = []

        for table in schema_analysis.tables:
            # Table header
            table_desc = f"- {table.name}: {table.table_type.title()} table"
            if table.row_count > 0:
                table_desc += f" ({table.row_count} rows)"
            lines.append(table_desc)

            # Columns with details
            for col in table.columns:
                col_desc = f"  - {col.name}: {col.sql_type}"
                if col.is_primary_key:
                    col_desc += " [PRIMARY KEY]"
                elif col.is_foreign_key:
                    col_desc += f" [FK → {col.foreign_table}.id]"
                if not col.is_nullable:
                    col_desc += " [NOT NULL]"
                lines.append(col_desc)

        return '\n'.join(lines)

    def _build_relationship_description(self, relationships: List[Dict[str, Any]]) -> str:
        """Build relationship description"""
        lines = []

        for rel in relationships:
            if rel.get('confidence', 0) >= 0.8:  # Only high-confidence relationships
                line = f"- {rel['from_table']}.{rel['from_column']} → {rel['to_table']}.{rel['to_column']}"
                lines.append(line)

        return '\n'.join(lines) if lines else "No explicit relationships defined"

    def _build_examples_section(self, examples: List) -> str:
        """Build examples section for prompt"""
        lines = []

        for i, example in enumerate(examples, 1):
            lines.append(f"{i}. Question: \"{example.question}\"")
            lines.append(f"   SQL: {example.sql}")
            lines.append("")

        return '\n'.join(lines)

    def get_adapted_context_for_query(self, query: str) -> Dict[str, Any]:
        """Get adapted context for a specific query"""
        if not self.current_domain:
            return {}

        context = {
            'schema_context': self._get_relevant_schema_context(query),
            'few_shot_examples': self._get_relevant_examples(query),
            'column_mappings': self.current_domain.dynamic_templates.column_mappings,
            'relationships': self.current_domain.dynamic_templates.table_relationships,
            'domain_info': {
                'name': self.current_domain.schema_name,
                'confidence_threshold': self.current_domain.confidence_threshold
            }
        }

        return context

    def _get_relevant_schema_context(self, query: str) -> List[Dict[str, Any]]:
        """Get schema context relevant to the query"""
        if not self.current_domain:
            return []

        relevant_tables = []
        query_lower = query.lower()

        # Find tables mentioned in query
        for table in self.current_domain.schema_analysis.tables:
            if table.name.lower() in query_lower or any(term in query_lower for term in table.domain_terms or []):
                table_context = {
                    'schema': {
                        'name': table.name,
                        'columns': [
                            {
                                'name': col.name,
                                'type': col.sql_type,
                                'semantic_type': col.semantic_type.value,
                                'primary_key': col.is_primary_key,
                                'foreign_key': f"{col.foreign_table}.id" if col.is_foreign_key else None,
                                'nullable': col.is_nullable
                            }
                            for col in table.columns
                        ],
                        'row_count': table.row_count,
                        'table_type': table.table_type
                    }
                }
                relevant_tables.append(table_context)

        # If no specific tables found, return all main entity tables
        if not relevant_tables:
            for table in self.current_domain.schema_analysis.tables:
                if table.table_type == 'entity':
                    table_context = {
                        'schema': {
                            'name': table.name,
                            'columns': [{'name': col.name, 'type': col.sql_type} for col in table.columns]
                        }
                    }
                    relevant_tables.append(table_context)

        return relevant_tables

    def _get_relevant_examples(self, query: str) -> List[Dict[str, Any]]:
        """Get few-shot examples relevant to the query"""
        if not self.current_domain:
            return []

        relevant_examples = []
        query_lower = query.lower()

        # Find examples with similar patterns
        for example in self.current_domain.dynamic_templates.few_shot_examples:
            # Check for keyword matches
            example_keywords = set(example.question.lower().split())
            query_keywords = set(query_lower.split())

            # Calculate similarity based on common keywords
            common_keywords = example_keywords.intersection(query_keywords)
            similarity = len(common_keywords) / max(len(query_keywords), 1)

            if similarity > 0.3 or any(keyword in query_lower for keyword in ['average', 'sum', 'count', 'total', 'by']):
                relevant_examples.append({
                    'question': example.question,
                    'sql': example.sql,
                    'explanation': example.explanation,
                    'similarity': similarity,
                    'confidence': example.confidence
                })

        # Sort by relevance and confidence
        relevant_examples.sort(key=lambda x: (x['similarity'], x['confidence']), reverse=True)
        return relevant_examples[:3]  # Return top 3

    def export_domain_configuration(self) -> Dict[str, Any]:
        """Export current domain configuration for persistence"""
        if not self.current_domain:
            return {}

        # Create exportable configuration
        config = {
            'schema_name': self.current_domain.schema_name,
            'database_path': self.current_domain.database_path,
            'confidence_threshold': self.current_domain.confidence_threshold,
            'use_smart_pipeline': self.current_domain.use_smart_pipeline,
            'schema_analysis': self._serialize_schema_analysis(self.current_domain.schema_analysis),
            'dynamic_templates': self._serialize_dynamic_templates(self.current_domain.dynamic_templates),
            'adapted_templates': self._serialize_adapted_templates()
        }

        return config

    def _serialize_schema_analysis(self, analysis: SchemaAnalysis) -> Dict[str, Any]:
        """Serialize schema analysis for export"""
        return {
            'database_name': analysis.database_name,
            'table_count': len(analysis.tables),
            'relationship_count': len(analysis.relationships),
            'domain_vocabulary_size': len(analysis.domain_vocabulary),
            'common_patterns': analysis.common_patterns,
            'suggested_queries': analysis.suggested_queries[:10]  # Limit size
        }

    def _serialize_dynamic_templates(self, templates: DynamicQueryTemplates) -> Dict[str, Any]:
        """Serialize dynamic templates for export"""
        return {
            'schema_name': templates.schema_name,
            'pattern_count': len(templates.patterns),
            'example_count': len(templates.few_shot_examples),
            'column_mapping_count': len(templates.column_mappings),
            'top_examples': [
                {
                    'question': ex.question,
                    'sql': ex.sql,
                    'confidence': ex.confidence
                }
                for ex in templates.few_shot_examples[:5]
            ]
        }

    def _serialize_adapted_templates(self) -> Dict[str, Any]:
        """Serialize adapted templates for export"""
        if not self.adapted_templates:
            return {}

        try:
            return {
                'few_shot_count': len(self.adapted_templates.FEW_SHOT_EXAMPLES),
                'column_mapping_count': len(self.adapted_templates.COLUMN_MAPPINGS),
                'relationship_count': len(self.adapted_templates.TABLE_RELATIONSHIPS)
            }
        except Exception as e:
            logger.warning(f"Failed to serialize adapted templates: {e}")
            return {'error': 'serialization_failed'}

    def is_adapted(self) -> bool:
        """Check if domain adapter has been initialized"""
        return self.current_domain is not None

    def get_domain_configuration(self) -> Optional[DomainConfiguration]:
        """Get the current domain configuration"""
        return self.current_domain

    def get_adaptation_summary(self) -> Dict[str, Any]:
        """Get summary of current adaptation"""
        if not self.current_domain:
            return {'status': 'not_adapted'}

        return {
            'status': 'adapted',
            'schema_name': self.current_domain.schema_name,
            'database_path': self.current_domain.database_path,
            'table_count': len(self.current_domain.schema_analysis.tables),
            'example_count': len(self.current_domain.dynamic_templates.few_shot_examples),
            'confidence_threshold': self.current_domain.confidence_threshold,
            'patterns': self.current_domain.schema_analysis.common_patterns,
            'domain_detected': self._detect_domain_from_analysis(self.current_domain.schema_analysis)
        }

    def _create_fallback_schema_analysis(self) -> 'SchemaAnalysis':
        """Create minimal fallback schema analysis when normal analysis fails"""
        try:
            # Try to get basic schema info from database provider
            schema_info = self.database_provider.get_schema()
            tables = []

            if schema_info:
                from .schema_discovery import TableInfo, ColumnInfo, SemanticType
                for table in schema_info:
                    columns = []
                    for col in table.columns:
                        columns.append(ColumnInfo(
                            name=col['name'],
                            sql_type=col['type'],
                            semantic_type=SemanticType.GENERIC,
                            is_nullable=col.get('nullable', True),
                            is_primary_key=col.get('primary_key', False),
                            is_foreign_key=False,
                            foreign_table=None
                        ))

                    tables.append(TableInfo(
                        name=table.name,
                        columns=columns,
                        row_count=table.row_count,
                        table_type='entity'
                    ))

            from .schema_discovery import SchemaAnalysis
            return SchemaAnalysis(
                database_name=getattr(self.database_provider, 'database_path', 'fallback_db'),
                tables=tables,
                relationships=[],
                domain_vocabulary={'general': ['data', 'record', 'table']},
                common_patterns=['basic_queries'],
                suggested_queries=['SELECT * FROM {table}', 'SELECT COUNT(*) FROM {table}']
            )
        except Exception as e:
            logger.error(f"Failed to create fallback schema analysis: {e}")
            # Return absolute minimal schema
            from .schema_discovery import SchemaAnalysis
            return SchemaAnalysis(
                database_name='fallback_database',
                tables=[],
                relationships=[],
                domain_vocabulary={'general': ['data']},
                common_patterns=[],
                suggested_queries=['SELECT 1']
            )

    def _create_fallback_templates(self, schema_analysis: 'SchemaAnalysis') -> 'DynamicQueryTemplates':
        """Create minimal fallback templates when normal generation fails"""
        try:
            from .dynamic_template_generator import DynamicQueryTemplates, QueryExample

            # Create basic examples based on available tables
            examples = []
            if schema_analysis.tables:
                for table in schema_analysis.tables[:3]:  # Limit to first 3 tables
                    examples.append(QueryExample(
                        question=f"Show all records from {table.name}",
                        sql=f"SELECT * FROM {table.name}",
                        pattern_type="basic_select",
                        explanation=f"Simple SELECT query for {table.name} table",
                        confidence=0.8
                    ))
            else:
                # Absolute fallback
                examples.append(QueryExample(
                    question="Show a test query",
                    sql="SELECT 1 as test",
                    pattern_type="basic_select",
                    explanation="Basic test query",
                    confidence=0.5
                ))

            return DynamicQueryTemplates(
                schema_name=schema_analysis.database_name,
                patterns=[],
                few_shot_examples=examples,
                column_mappings={},
                table_relationships=[]
            )
        except Exception as e:
            logger.error(f"Failed to create fallback templates: {e}")
            # Return absolute minimal templates
            from .dynamic_template_generator import DynamicQueryTemplates, QueryExample
            return DynamicQueryTemplates(
                schema_name='fallback',
                patterns=[],
                few_shot_examples=[QueryExample(
                    question="Basic query",
                    sql="SELECT 1",
                    pattern_type="basic",
                    explanation="Minimal query",
                    confidence=0.1
                )],
                column_mappings={},
                table_relationships=[]
            )

    def _create_fallback_adapted_templates(self) -> QueryTemplates:
        """Create fallback adapted templates when normal adaptation fails"""
        try:
            # Create basic QueryTemplates without domain adapter
            adapted = QueryTemplates()

            # Set minimal content
            adapted.set_dynamic_content(
                examples=[{
                    'question': 'Show test data',
                    'sql': 'SELECT 1 as test',
                    'explanation': 'Basic fallback query'
                }],
                column_mappings={},
                relationships={}
            )

            return adapted
        except Exception as e:
            logger.error(f"Failed to create fallback adapted templates: {e}")
            # Return basic QueryTemplates
            return QueryTemplates()

    def _create_minimal_fallback_configuration(self) -> DomainConfiguration:
        """Create minimal fallback configuration when all else fails"""
        try:
            schema_analysis = self._create_fallback_schema_analysis()
            dynamic_templates = self._create_fallback_templates(schema_analysis)

            return DomainConfiguration(
                schema_name='fallback_domain',
                database_path=getattr(self.database_provider, 'database_path', 'unknown'),
                schema_analysis=schema_analysis,
                dynamic_templates=dynamic_templates,
                confidence_threshold=0.1,
                use_smart_pipeline=False
            )
        except Exception as e:
            logger.error(f"Failed to create minimal fallback configuration: {e}")
            # This should never fail - return absolute minimal config
            from .schema_discovery import SchemaAnalysis
            from .dynamic_template_generator import DynamicQueryTemplates, QueryExample

            minimal_schema = SchemaAnalysis(
                database_name='minimal_fallback',
                tables=[],
                relationships=[],
                domain_vocabulary={},
                common_patterns=[],
                suggested_queries=[]
            )

            minimal_templates = DynamicQueryTemplates(
                schema_name='minimal_fallback',
                patterns=[],
                few_shot_examples=[],
                column_mappings={},
                table_relationships=[]
            )

            return DomainConfiguration(
                schema_name='minimal_fallback',
                database_path='unknown',
                schema_analysis=minimal_schema,
                dynamic_templates=minimal_templates,
                confidence_threshold=0.0,
                use_smart_pipeline=False
            )