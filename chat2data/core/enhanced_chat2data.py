"""Enhanced Chat2Data with smart query pipeline and schema-agnostic adaptation"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from .base import LLMProvider, DatabaseProvider, VectorStoreProvider, QueryResult, SchemaInfo
from .schema_discovery import SchemaDiscoveryEngine, SchemaAnalysis
from .dynamic_template_generator import DynamicTemplateGenerator, DynamicQueryTemplates
from .domain_adapter import DomainAdapter, DomainConfiguration
from ..config.adaptive_config_manager import AdaptiveConfigManager, AdaptiveConfig

logger = logging.getLogger(__name__)


class EnhancedChat2Data:
    """Enhanced Chat2Data with smart query pipeline, LLM integration, and schema-agnostic adaptation"""

    def __init__(
        self,
        llm_provider: LLMProvider,
        database_provider: DatabaseProvider,
        vector_store_provider: Optional[VectorStoreProvider] = None,
        use_smart_pipeline: bool = True,
        enable_schema_adaptation: bool = True,
        config_manager: Optional[AdaptiveConfigManager] = None
    ):
        """
        Initialize Enhanced Chat2Data with schema-agnostic capabilities

        Args:
            llm_provider: LLM provider for generating SQL
            database_provider: Database provider for executing queries
            vector_store_provider: Optional vector store for semantic search
            use_smart_pipeline: Enable smart query pipeline features
            enable_schema_adaptation: Enable automatic schema adaptation
            config_manager: Optional adaptive configuration manager
        """
        self.llm = llm_provider
        self.database = database_provider
        self.vector_store = vector_store_provider
        self.use_smart_pipeline = use_smart_pipeline
        self.enable_schema_adaptation = enable_schema_adaptation

        # Schema-agnostic components
        self.domain_adapter: Optional[DomainAdapter] = None
        self.config_manager = config_manager or AdaptiveConfigManager()
        self.schema_discovery_engine = SchemaDiscoveryEngine(database_provider)
        self.template_generator = DynamicTemplateGenerator()

        # State management
        self._schema_indexed = False
        self._schema_adapted = False
        self._query_cache = {}
        self._current_domain_config: Optional[DomainConfiguration] = None

        # Connect LLM with vector store for enhanced context
        if hasattr(llm_provider, 'set_vector_store') and vector_store_provider:
            llm_provider.set_vector_store(vector_store_provider)

        # Connect LLM with database provider for relationship detection
        if hasattr(llm_provider, 'set_database_provider'):
            llm_provider.set_database_provider(database_provider)

        # Initialize domain adapter if schema adaptation is enabled
        if enable_schema_adaptation:
            self.domain_adapter = DomainAdapter(database_provider)

            # Connect domain adapter with LLM provider for dynamic prompts
            if hasattr(llm_provider, 'set_domain_adapter'):
                llm_provider.set_domain_adapter(self.domain_adapter)
                logger.info("Domain adapter connected to LLM provider for dynamic prompts")

            logger.info("Schema adaptation enabled - system will automatically adapt to database schema")

    async def query(self, natural_language_query: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Smart query pipeline with enhanced LLM processing and schema adaptation

        Args:
            natural_language_query: User's natural language query
            use_cache: Whether to use cached results for repeated queries

        Returns:
            Dict with query results, SQL, metadata, and confidence scores
        """
        try:
            # Check cache
            if use_cache and natural_language_query in self._query_cache:
                logger.info(f"Using cached result for: {natural_language_query}")
                return self._query_cache[natural_language_query]

            # Step 0: Ensure schema adaptation is complete
            if self.enable_schema_adaptation and not self._schema_adapted:
                await self._ensure_schema_adaptation()

            # Ensure schema is indexed
            if not self._schema_indexed:
                await self._ensure_schema_indexed()

            # Step 1: Query Analysis
            query_analysis = await self._analyze_query(natural_language_query)

            # Step 2: Get Enhanced Context (now includes domain-adapted context)
            context = await self._get_enhanced_context(
                natural_language_query,
                query_analysis
            )

            # Step 3: Generate SQL with confidence scoring (using adapted templates)
            sql_result = await self._generate_sql_with_confidence(
                natural_language_query,
                context
            )

            # Step 4: Validate and potentially refine SQL
            validated_sql = await self._validate_and_refine_sql(
                sql_result['sql'],
                natural_language_query,
                context
            )

            # Step 5: Execute Query
            execution_result = await self._execute_with_retry(validated_sql)

            # Step 6: Post-process results
            final_result = await self._post_process_results(
                execution_result,
                natural_language_query,
                validated_sql,
                sql_result.get('confidence', 0)
            )

            # Cache successful results
            if final_result['success'] and use_cache:
                self._query_cache[natural_language_query] = final_result

            return final_result

        except Exception as e:
            logger.error(f"Error in smart query pipeline: {str(e)}")
            return {
                "success": False,
                "query": natural_language_query,
                "error": str(e),
                "pipeline_stage": "unknown"
            }

    async def _analyze_query(self, query: str) -> Dict[str, Any]:
        """Analyze query intent and complexity"""
        analysis = {
            'complexity': 'simple',  # simple, moderate, complex
            'operation_type': 'select',  # select, aggregate, join, etc.
            'requires_grouping': False,
            'requires_joining': False,
            'requires_aggregation': False,
            'confidence_keywords': []
        }

        query_lower = query.lower()

        # Detect aggregation
        aggregation_keywords = ['count', 'sum', 'average', 'avg', 'total', 'max', 'min']
        if any(keyword in query_lower for keyword in aggregation_keywords):
            analysis['requires_aggregation'] = True
            analysis['complexity'] = 'moderate'
            analysis['confidence_keywords'].extend([k for k in aggregation_keywords if k in query_lower])

        # Detect grouping
        grouping_keywords = ['by category', 'by type', 'group by', 'per', 'each']
        if any(keyword in query_lower for keyword in grouping_keywords):
            analysis['requires_grouping'] = True
            analysis['complexity'] = 'moderate'
            analysis['confidence_keywords'].extend([k for k in grouping_keywords if k in query_lower])

        # Detect joining
        joining_keywords = ['with their', 'and their', 'including', 'along with', 'related']
        if any(keyword in query_lower for keyword in joining_keywords):
            analysis['requires_joining'] = True
            analysis['complexity'] = 'complex'
            analysis['confidence_keywords'].extend([k for k in joining_keywords if k in query_lower])

        # Detect operation type
        if 'top' in query_lower or 'first' in query_lower or 'last' in query_lower:
            analysis['operation_type'] = 'limit'
        elif any(k in query_lower for k in aggregation_keywords):
            analysis['operation_type'] = 'aggregate'
        elif 'all' in query_lower or 'list' in query_lower:
            analysis['operation_type'] = 'select_all'

        logger.info(f"Query analysis: {analysis}")
        return analysis

    async def _get_enhanced_context(self, query: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Get enhanced context using vector store, analysis, and domain adaptation"""
        context = {
            'schema': [],
            'similar_queries': [],
            'relevant_tables': [],
            'analysis': analysis,
            'domain_context': {}
        }

        # Get domain-adapted context if available
        if self.domain_adapter and self.domain_adapter.is_adapted():
            try:
                domain_context = self.domain_adapter.get_adapted_context_for_query(query)
                context['domain_context'] = domain_context
                context['schema'] = domain_context.get('schema_context', [])
                context['domain_examples'] = domain_context.get('few_shot_examples', [])
                logger.info(f"Using domain-adapted context: {len(context['schema'])} schemas, {len(context.get('domain_examples', []))} examples")
            except Exception as e:
                logger.warning(f"Failed to get domain context: {e}")

        # Fallback to standard vector store context if no domain context
        if not context['schema'] and self.vector_store:
            # Get more schemas for complex queries
            k = 5 if analysis['complexity'] == 'complex' else 3

            # Get relevant schemas
            relevant_schemas = self.vector_store.search_relevant_schema(query, k=k)
            context['schema'] = relevant_schemas
            context['relevant_tables'] = [s['schema'].get('name') for s in relevant_schemas if 'schema' in s]

            # Get similar queries for learning
            similar = self.vector_store.get_similar_queries(query, k=3)
            if similar:
                context['similar_queries'] = similar

            # If query requires joining, ensure we have related tables
            if analysis['requires_joining'] and len(context['relevant_tables']) > 0:
                # Try to find related tables
                for table_name in context['relevant_tables'][:2]:
                    related = self.vector_store.search_relevant_schema(f"related to {table_name}", k=2)
                    for rel in related:
                        if rel not in context['schema']:
                            context['schema'].append(rel)

        # Final fallback: use all schema
        if not context['schema']:
            schema_info = self.database.get_schema()
            context['schema'] = [{"schema": info.model_dump()} for info in schema_info]

        logger.info(f"Enhanced context: {len(context['schema'])} schemas, {len(context['similar_queries'])} similar queries")
        return context

    async def _generate_sql_with_confidence(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate SQL with confidence scoring"""
        # Generate SQL
        sql = await self.llm.generate_sql(query, context['schema'])

        # Calculate confidence score
        confidence = self._calculate_confidence(sql, context)

        return {
            'sql': sql,
            'confidence': confidence,
            'context_used': len(context['schema'])
        }

    def _calculate_confidence(self, sql: str, context: Dict[str, Any]) -> float:
        """Calculate confidence score for generated SQL"""
        confidence = 0.5  # Base confidence

        # Check if SQL uses tables from context
        if context.get('relevant_tables'):
            for table in context['relevant_tables']:
                if table.lower() in sql.lower():
                    confidence += 0.1

        # Check if similar queries exist
        if context.get('similar_queries'):
            confidence += 0.2

        # Check query complexity matches SQL complexity
        analysis = context.get('analysis', {})
        sql_upper = sql.upper()

        if analysis.get('requires_aggregation') and any(func in sql_upper for func in ['COUNT', 'SUM', 'AVG', 'MAX', 'MIN']):
            confidence += 0.1

        if analysis.get('requires_grouping') and 'GROUP BY' in sql_upper:
            confidence += 0.1

        if analysis.get('requires_joining') and 'JOIN' in sql_upper:
            confidence += 0.1

        # Cap at 0.95
        return min(confidence, 0.95)

    async def _validate_and_refine_sql(self, sql: str, query: str, context: Dict[str, Any]) -> str:
        """Validate SQL and potentially refine it"""
        # Basic validation
        is_safe, message = self.database.validate_sql(sql)

        if not is_safe:
            logger.warning(f"SQL validation failed: {message}")
            # Try to regenerate with stricter prompt
            if self.use_smart_pipeline:
                logger.info("Attempting to regenerate SQL with stricter validation...")
                refined_sql = await self.llm.generate_sql(
                    f"Generate a safe SELECT-only SQL query for: {query}",
                    context['schema']
                )
                is_safe, _ = self.database.validate_sql(refined_sql)
                if is_safe:
                    return refined_sql

            raise ValueError(f"SQL validation failed: {message}")

        return sql

    async def _execute_with_retry(self, sql: str, max_retries: int = 2) -> QueryResult:
        """Execute SQL with retry logic"""
        for attempt in range(max_retries):
            try:
                result = self.database.execute_query(sql)
                if result.success:
                    return result

                if attempt < max_retries - 1:
                    logger.warning(f"Query failed (attempt {attempt + 1}): {result.error}")
                    await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff

            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Execution error (attempt {attempt + 1}): {e}")
                await asyncio.sleep(0.5 * (attempt + 1))

        return QueryResult(success=False, error="Max retries exceeded")

    async def _post_process_results(
        self,
        execution_result: QueryResult,
        query: str,
        sql: str,
        confidence: float
    ) -> Dict[str, Any]:
        """Post-process and enhance results"""
        result = {
            "success": execution_result.success,
            "query": query,
            "sql": sql,
            "result": execution_result.model_dump(),
            "confidence": confidence,
            "metadata": {
                "row_count": len(execution_result.data) if execution_result.data else 0,
                "execution_time": execution_result.execution_time if hasattr(execution_result, 'execution_time') else None,
                "used_smart_pipeline": self.use_smart_pipeline
            }
        }

        # Store successful query for learning
        if execution_result.success and self.vector_store:
            self.vector_store.store_query_example(query, sql)

        # Generate summary if we have data
        if execution_result.success and execution_result.data:
            try:
                summary = await self.llm.generate_summary(execution_result.data, query)

                # Validate summary doesn't contain SQL
                if summary and any(keyword in summary.upper() for keyword in ['SELECT ', 'FROM ', 'WHERE ', 'JOIN ', 'LIMIT ']):
                    logger.warning(f"Summary contained SQL keywords, replacing with fallback")
                    summary = f"Found {len(execution_result.data)} results for your query."

                # Additional check for summaries that ARE SQL queries
                if summary and summary.strip().upper().startswith(('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'WITH')):
                    logger.warning(f"Summary was a SQL query, replacing with fallback")
                    summary = f"Found {len(execution_result.data)} results for your query."

                result["summary"] = summary
            except Exception as e:
                logger.warning(f"Failed to generate summary: {e}")
                # Provide a fallback summary
                result["summary"] = f"Found {len(execution_result.data)} results for your query."

        # Add insights for empty results
        if execution_result.success and not execution_result.data:
            result["insights"] = "Query executed successfully but returned no results. This might mean no data matches your criteria."

        return result

    async def _ensure_schema_indexed(self):
        """Ensure database schema is indexed in vector store"""
        if self.vector_store and not self._schema_indexed:
            try:
                logger.info("Indexing database schema in vector store...")
                schema = self.database.get_schema()
                if schema:
                    self.vector_store.index_schema(schema)
                    self._schema_indexed = True
                    logger.info(f"Successfully indexed {len(schema)} tables")
            except Exception as e:
                logger.warning(f"Failed to index schema: {e}")

    async def _ensure_schema_adaptation(self):
        """Ensure schema adaptation is complete"""
        if not self._schema_adapted and self.domain_adapter:
            try:
                logger.info("Starting automatic schema adaptation...")

                # Perform domain analysis and adaptation
                self._current_domain_config = await self.domain_adapter.analyze_and_adapt()

                # Create or update adaptive configuration
                database_path = getattr(self.database, 'database_path', 'unknown')
                adaptive_config = self.config_manager.create_adaptive_config(
                    database_path=database_path,
                    domain_config=self._current_domain_config,
                    environment="runtime"
                )

                # Update LLM provider with domain-specific context if supported
                if hasattr(self.llm, 'update_system_prompt') and self._current_domain_config:
                    domain_prompt = getattr(self._current_domain_config, 'system_prompt', None)
                    if domain_prompt:
                        self.llm.update_system_prompt(domain_prompt)

                self._schema_adapted = True
                logger.info(f"Schema adaptation completed for domain: {self._current_domain_config.schema_name}")

            except Exception as e:
                logger.warning(f"Schema adaptation failed, continuing with standard pipeline: {e}")
                self._schema_adapted = True  # Mark as attempted to avoid retrying

    def get_schema(self) -> List[SchemaInfo]:
        """Get database schema information"""
        return self.database.get_schema()

    def get_similar_queries(self, query: str, k: int = 5) -> List[Any]:
        """Get similar queries from history"""
        if self.vector_store:
            return self.vector_store.get_similar_queries(query, k)
        return []

    def clear_cache(self):
        """Clear query cache"""
        self._query_cache.clear()
        logger.info("Query cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "cache_size": len(self._query_cache),
            "cached_queries": list(self._query_cache.keys())
        }

    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check of all components including schema adaptation"""
        health = {
            "llm": {
                "name": self.llm.name,
                "available": self.llm.is_available(),
            },
            "database": {
                "name": self.database.name,
                "connected": self.database.is_connected(),
                "schema_loaded": len(self.get_schema()) > 0
            },
            "smart_pipeline": {
                "enabled": self.use_smart_pipeline,
                "cache_size": len(self._query_cache)
            }
        }

        if self.vector_store:
            health["vector_store"] = {
                "name": self.vector_store.name,
                "schema_indexed": self._schema_indexed,
                "available": True
            }

        # Schema adaptation health
        if self.enable_schema_adaptation:
            health["schema_adaptation"] = {
                "enabled": True,
                "adapted": self._schema_adapted,
                "domain_config_loaded": self._current_domain_config is not None,
                "domain_name": self._current_domain_config.schema_name if self._current_domain_config else None,
                "adaptation_status": self.get_adaptation_status()
            }

        # Configuration management
        health["configuration"] = {
            "manager_available": self.config_manager is not None,
            "active_config": self.config_manager.get_active_config().config_name if self.config_manager.get_active_config() else None
        }

        # Overall health status
        components_healthy = [
            health["llm"]["available"],
            health["database"]["connected"],
            health["database"]["schema_loaded"]
        ]

        if self.enable_schema_adaptation:
            components_healthy.append(health["schema_adaptation"]["adapted"])

        health["overall_status"] = "healthy" if all(components_healthy) else "degraded"

        return health

    def force_reindex_schema(self):
        """Force re-indexing of schema"""
        self._schema_indexed = False
        self.clear_cache()
        logger.info("Schema will be re-indexed on next query")

    def get_adaptation_status(self) -> Dict[str, Any]:
        """Get current schema adaptation status"""
        if not self.enable_schema_adaptation:
            return {"status": "disabled", "message": "Schema adaptation is disabled"}

        if not self._schema_adapted:
            return {"status": "pending", "message": "Schema adaptation not yet performed"}

        if not self.domain_adapter or not self.domain_adapter.is_adapted():
            return {"status": "failed", "message": "Domain adapter failed to initialize"}

        if self._current_domain_config:
            return {
                "status": "adapted",
                "message": "Schema successfully adapted",
                "domain": self._current_domain_config.schema_name,
                "summary": self.domain_adapter.get_adaptation_summary()
            }

        return {"status": "unknown", "message": "Adaptation status unclear"}

    def get_domain_configuration(self) -> Optional[DomainConfiguration]:
        """Get current domain configuration"""
        return self._current_domain_config

    def force_schema_adaptation(self) -> bool:
        """Force re-adaptation of schema"""
        if not self.enable_schema_adaptation or not self.domain_adapter:
            return False

        try:
            self._schema_adapted = False
            self._current_domain_config = None
            self.clear_cache()
            logger.info("Schema adaptation will be re-performed on next query")
            return True
        except Exception as e:
            logger.error(f"Failed to reset schema adaptation: {e}")
            return False

    def export_current_configuration(self, export_path: str) -> bool:
        """Export current configuration for sharing"""
        try:
            if not self.domain_adapter or not self.domain_adapter.is_adapted():
                logger.warning("No adapted configuration to export")
                return False

            config_data = self.domain_adapter.export_domain_configuration()
            self.config_manager.export_configuration(
                self.config_manager.get_active_config().config_name if self.config_manager.get_active_config() else "current",
                export_path
            )
            logger.info(f"Configuration exported to: {export_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to export configuration: {e}")
            return False

    def get_system_info(self) -> Dict[str, Any]:
        """Get comprehensive system information"""
        info = {
            "version": "Enhanced Chat2Data v2.0",
            "features": {
                "smart_pipeline": self.use_smart_pipeline,
                "schema_adaptation": self.enable_schema_adaptation,
                "vector_store": self.vector_store is not None,
                "configuration_management": True
            },
            "schema_adaptation": self.get_adaptation_status() if self.enable_schema_adaptation else None,
            "cache_stats": self.get_cache_stats(),
            "database_info": {
                "name": self.database.name,
                "connected": self.database.is_connected(),
                "schema_tables": len(self.get_schema())
            }
        }

        if self._current_domain_config:
            info["domain_info"] = {
                "schema_name": self._current_domain_config.schema_name,
                "confidence_threshold": self._current_domain_config.confidence_threshold,
                "use_smart_pipeline": self._current_domain_config.use_smart_pipeline
            }

        return info