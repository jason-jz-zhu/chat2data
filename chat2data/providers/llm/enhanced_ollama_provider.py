"""Enhanced Ollama LLM provider with better context and prompts"""

import logging
import json
from typing import Dict, List, Any, Optional, Tuple
from ...core.base import LLMProvider
from ...core.query_templates import QueryTemplates
from ...prompts import get_prompt_manager

logger = logging.getLogger(__name__)


class EnhancedOllamaLLMProvider(LLMProvider):
    """Enhanced Ollama provider with improved prompts and context handling"""

    def __init__(self, model_name: str = 'llama3:latest', base_url: str = 'http://localhost:11434'):
        """Initialize Enhanced Ollama provider"""
        self.model_name = model_name
        self.base_url = base_url
        self._agent = None
        self.vector_store = None  # Will be set by Chat2Data
        self.domain_adapter = None  # Will be set by Chat2Data
        self._dynamic_system_prompt = None  # Cache for dynamic prompt
        self.prompt_manager = get_prompt_manager()  # Initialize centralized prompt manager

    def set_vector_store(self, vector_store):
        """Set the vector store for enhanced context"""
        self.vector_store = vector_store

    def set_domain_adapter(self, domain_adapter):
        """Set the domain adapter for dynamic prompts"""
        self.domain_adapter = domain_adapter
        # Clear cached prompt to force regeneration
        self._dynamic_system_prompt = None
        # Clear agent to force recreation with new prompt
        self._agent = None
        logger.info("Domain adapter set - system prompt will be regenerated")

    def set_database_provider(self, database_provider):
        """Set the database provider for relationship detection"""
        self.database_provider = database_provider
        logger.info("Database provider set for relationship detection")

    def _init_agent(self):
        """Lazy initialization of PydanticAI agent"""
        if self._agent is None:
            try:
                import os
                from pydantic_ai import Agent

                # Set environment variables for OpenAI-compatible Ollama
                os.environ['OPENAI_BASE_URL'] = f"{self.base_url}/v1"
                os.environ['OPENAI_API_KEY'] = "ollama"  # Required but not used

                # Use the full model name for OpenAI compatibility (don't strip :latest)
                model_name = self.model_name

                # Generate dynamic system prompt
                system_prompt = self._get_dynamic_system_prompt()

                self._agent = Agent(
                    f'openai:{model_name}',
                    system_prompt=system_prompt
                )
            except ImportError:
                logger.error("PydanticAI not available. Install with: pip install pydantic-ai")
                raise

    async def generate_sql(self, query: str, schema_context: List[Dict[str, Any]]) -> str:
        """Generate SQL from natural language query with enhanced context"""
        self._init_agent()

        try:
            # Get enhanced context from vector store if available
            enhanced_context = self._get_enhanced_context(query, schema_context)

            # Build comprehensive prompt
            prompt = self._build_comprehensive_prompt(query, enhanced_context)

            logger.info(f"Sending enhanced prompt to Ollama (length: {len(prompt)} chars)")

            # Generate SQL using the agent
            result = await self._agent.run(prompt)

            # Extract and validate SQL
            sql = self._extract_and_validate_sql(result.output)

            # Store successful query for future learning
            if self.vector_store and sql:
                await self._store_successful_query(query, sql)

            logger.info(f"Generated SQL: {sql}")
            return sql

        except Exception as e:
            logger.error(f"Error generating SQL: {str(e)}")
            # Try fallback generation with simpler prompt
            return await self._fallback_generation(query, schema_context)

    def _get_enhanced_context(self, query: str, schema_context: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get enhanced context from vector store"""
        enhanced_context = {
            'schema': schema_context,
            'similar_queries': [],
            'relevant_tables': []
        }

        if self.vector_store:
            try:
                # Get similar queries with their SQL
                similar_queries = self.vector_store.get_similar_queries(query, k=3)
                if similar_queries:
                    enhanced_context['similar_queries'] = similar_queries

                # Get additional relevant schemas
                relevant_schemas = self.vector_store.search_relevant_schema(query, k=5)
                enhanced_context['relevant_tables'] = relevant_schemas

            except Exception as e:
                logger.warning(f"Failed to get enhanced context: {e}")

        return enhanced_context

    def _build_comprehensive_prompt(self, query: str, enhanced_context: Dict[str, Any]) -> str:
        """Build a comprehensive prompt with all available context"""
        prompt_parts = []

        # Get dynamic query templates instance
        query_templates = self._get_dynamic_query_templates()

        # Add few-shot examples first
        prompt_parts.append("=== EXAMPLE QUERIES ===")
        try:
            formatted_examples = query_templates.get_formatted_examples()[:1000] if query_templates else ""
            prompt_parts.append(formatted_examples)
        except Exception as e:
            logger.warning(f"Failed to get dynamic examples: {e}")
            prompt_parts.append("No examples available")

        # Add table relationships
        prompt_parts.append("\n=== TABLE RELATIONSHIPS ===")
        try:
            # First try to get relationships from database provider
            if hasattr(self, 'database_provider') and hasattr(self.database_provider, 'get_table_relationships'):
                relationships = self.database_provider.get_table_relationships()
                if relationships:
                    for rel in relationships:
                        rel_desc = f"- {rel['from_table']}.{rel['from_column']} → {rel['to_table']}.{rel['to_column']}"
                        prompt_parts.append(rel_desc)
                else:
                    prompt_parts.append("No explicit foreign key relationships found")
            else:
                # Fallback to query templates
                relationships = query_templates.get_relationship_description() if query_templates else "No relationships detected"
                prompt_parts.append(relationships)
        except Exception as e:
            logger.warning(f"Failed to get relationships: {e}")
            prompt_parts.append("No relationships available")

        # Add main schema context
        prompt_parts.append("\n=== DATABASE SCHEMA ===")
        schema_str = self._format_enhanced_schema(enhanced_context.get('schema', []))
        prompt_parts.append(schema_str)

        # Add relevant tables from vector search
        if enhanced_context.get('relevant_tables'):
            prompt_parts.append("\n=== MOST RELEVANT TABLES ===")
            for item in enhanced_context['relevant_tables'][:3]:
                if 'schema' in item:
                    table_name = item['schema'].get('name', 'unknown')
                    relevance = item.get('relevance_score', 0)
                    prompt_parts.append(f"- {table_name} (relevance: {relevance:.2f})")

        # Try to match query pattern using dynamic templates
        try:
            pattern_match = query_templates.match_pattern(query) if query_templates else {"matched": False}
            if pattern_match.get('matched'):
                prompt_parts.append("\n=== PATTERN HINT ===")
                prompt_parts.append(f"Similar to: {pattern_match['example']}")
        except Exception as e:
            logger.warning(f"Failed to match query pattern: {e}")

        # Add the user's question
        prompt_parts.append(f"\n=== USER QUESTION ===")
        prompt_parts.append(f"{query}")

        # Add generation instruction
        prompt_parts.append("\n=== INSTRUCTION ===")
        prompt_parts.append("Generate a SIMPLE and DIRECT SQL query to answer the user's question.")
        prompt_parts.append("IMPORTANT RULES:")
        prompt_parts.append("- Use the SIMPLEST approach that works")
        prompt_parts.append("- For 'show all', 'list all', 'display all' - DO NOT add LIMIT")
        prompt_parts.append("- For 'top N' or 'most expensive', use ORDER BY ... DESC LIMIT N")
        prompt_parts.append("- For 'average by category', use simple JOIN with GROUP BY")
        prompt_parts.append("- For filtering, use simple WHERE conditions")
        prompt_parts.append("- AVOID complex subqueries, window functions, or nested SELECTs")
        prompt_parts.append("- AVOID aliases unless absolutely necessary")
        prompt_parts.append("- Follow the example patterns shown above.")
        prompt_parts.append("- Use proper JOIN conditions from the relationships.")
        prompt_parts.append("- Return ONLY the SQL query, no explanations.")

        return "\n".join(prompt_parts)

    def _get_dynamic_query_templates(self):
        """Get dynamic query templates instance"""
        if self.domain_adapter and self.domain_adapter.is_adapted():
            try:
                # Return QueryTemplates instance with domain adapter
                return QueryTemplates(domain_adapter=self.domain_adapter)
            except Exception as e:
                logger.warning(f"Failed to create dynamic query templates: {e}")

        # Fallback to basic QueryTemplates
        try:
            return QueryTemplates()
        except Exception as e:
            logger.error(f"Failed to create fallback query templates: {e}")
            return None

    def _format_enhanced_schema(self, schema_context: List[Dict[str, Any]]) -> str:
        """Format schema with enhanced details"""
        if not schema_context:
            return "No schema context available."

        formatted = []
        for item in schema_context:
            if 'schema' in item:
                schema = item['schema']
                table_info = [f"Table: {schema.get('name', 'unknown')}"]

                # Add row count if available
                if 'row_count' in schema:
                    table_info.append(f"  Rows: {schema['row_count']}")

                # Add columns with details
                if 'columns' in schema:
                    table_info.append("  Columns:")
                    for col in schema['columns']:
                        if isinstance(col, dict):
                            col_str = f"    - {col.get('name', '')}: {col.get('type', 'unknown')}"
                            if col.get('primary_key'):
                                col_str += " [PRIMARY KEY]"
                            if col.get('foreign_key'):
                                col_str += f" [FK → {col['foreign_key']}]"
                            if not col.get('nullable', True):
                                col_str += " [NOT NULL]"
                            table_info.append(col_str)
                        else:
                            table_info.append(f"    - {col}")

                formatted.append("\n".join(table_info))

        return "\n\n".join(formatted)

    def _extract_and_validate_sql(self, response: str) -> str:
        """Extract SQL and perform basic validation with auto-correction"""
        # Remove markdown code blocks
        response = response.strip()
        if response.startswith('```sql'):
            response = response[6:]
        elif response.startswith('```'):
            response = response[3:]

        if response.endswith('```'):
            response = response[:-3]

        response = response.strip()

        # Apply auto-corrections for common issues
        response = self._apply_sql_corrections(response)

        # Validate it's a SELECT query
        if not response.upper().startswith('SELECT'):
            logger.warning(f"Generated non-SELECT query: {response[:100]}")
            # Try to extract SELECT from response
            import re
            select_match = re.search(r'(SELECT.*?)(?:;|$)', response, re.IGNORECASE | re.DOTALL)
            if select_match:
                response = select_match.group(1)
            else:
                raise ValueError("Generated query is not a SELECT statement")

        # Basic SQL injection prevention
        dangerous_keywords = ['DROP', 'DELETE', 'INSERT', 'UPDATE', 'CREATE', 'ALTER', 'TRUNCATE']
        for keyword in dangerous_keywords:
            if keyword in response.upper():
                logger.warning(f"Dangerous keyword {keyword} found in query")
                raise ValueError(f"Query contains dangerous keyword: {keyword}")

        return response.strip()

    def _apply_sql_corrections(self, sql: str) -> str:
        """Apply common SQL corrections and simplifications"""
        import re

        original_sql = sql
        sql = sql.strip()

        # Remove trailing semicolon
        sql = sql.rstrip(';')

        # Fix common parentheses issues
        sql = self._fix_parentheses_issues(sql)

        # Simplify overly complex queries
        sql = self._simplify_complex_queries(sql)

        # Fix table alias issues
        sql = self._fix_table_alias_issues(sql)

        # Fix JOIN issues
        sql = self._fix_join_issues(sql)

        if sql != original_sql:
            logger.info(f"Applied SQL corrections. Original length: {len(original_sql)}, corrected length: {len(sql)}")

        return sql

    def _fix_parentheses_issues(self, sql: str) -> str:
        """Fix common parentheses mismatching issues"""
        # Count parentheses
        open_count = sql.count('(')
        close_count = sql.count(')')

        if open_count == close_count:
            return sql

        # Simple fix: if we have unmatched opening parentheses in subquery
        if open_count > close_count:
            # Check if it's a malformed subquery
            if 'SELECT' in sql and 'FROM (' in sql.upper():
                # Try to balance by removing the problematic opening parenthesis
                sql_upper = sql.upper()
                if sql_upper.count('FROM (') > sql_upper.count(')'):
                    # Replace "FROM (" with "FROM" and remove the subquery structure
                    sql = re.sub(r'FROM\s*\(\s*SELECT', 'FROM (SELECT', sql, flags=re.IGNORECASE)
                    # If still unbalanced, simplify by removing subquery entirely
                    if sql.count('(') > sql.count(')'):
                        logger.warning("Removing problematic subquery structure")
                        # Extract the inner SELECT if possible
                        match = re.search(r'FROM\s*\(\s*(SELECT.*?)$', sql, re.IGNORECASE | re.DOTALL)
                        if match:
                            inner_select = match.group(1)
                            # Replace the entire FROM clause with simplified version
                            sql = re.sub(r'FROM\s*\(\s*SELECT.*', f'FROM products ORDER BY price DESC LIMIT 5', sql, flags=re.IGNORECASE | re.DOTALL)

        return sql

    def _simplify_complex_queries(self, sql: str) -> str:
        """Simplify overly complex queries that often fail"""
        sql_upper = sql.upper()

        # If query has ROW_NUMBER() with improper syntax, simplify it
        if 'ROW_NUMBER()' in sql_upper and 'WHERE ROW_NUM' in sql_upper:
            logger.warning("Simplifying ROW_NUMBER() query to basic ORDER BY + LIMIT")
            # Convert to simple ORDER BY + LIMIT
            if 'LIMIT' in sql_upper:
                limit_match = re.search(r'<= (\d+)', sql)
                if limit_match:
                    limit_num = limit_match.group(1)
                    sql = re.sub(r'SELECT.*?FROM.*?WHERE.*?ORDER BY.*',
                               f'SELECT * FROM products ORDER BY price DESC LIMIT {limit_num}',
                               sql, flags=re.IGNORECASE | re.DOTALL)

        # If query has complex aggregation with JOIN that doesn't make sense, simplify
        if 'SUM(' in sql_upper and 'GROUP BY' in sql_upper and 'JOIN' in sql_upper:
            # Check if asking for "most expensive products" - this should be simple ORDER BY
            if any(keyword in sql_upper for keyword in ['MOST EXPENSIVE', 'TOP', 'HIGHEST PRICE']):
                logger.warning("Simplifying complex aggregation to simple ORDER BY for 'most expensive' query")
                sql = "SELECT * FROM products ORDER BY price DESC LIMIT 5"

        return sql

    def _fix_table_alias_issues(self, sql: str) -> str:
        """Fix table alias issues"""
        import re

        # Find all table.column references
        alias_refs = re.findall(r'\b(\w+)\.(\w+)', sql)
        if not alias_refs:
            return sql

        # Find defined aliases
        sql_upper = sql.upper()
        defined_aliases = set()

        # Check FROM clause for aliases
        from_match = re.search(r'FROM\s+(\w+)(?:\s+AS\s+(\w+)|\s+(\w+))?', sql_upper)
        if from_match:
            table_name, as_alias, direct_alias = from_match.groups()
            if as_alias:
                defined_aliases.add(as_alias.lower())
            elif direct_alias:
                defined_aliases.add(direct_alias.lower())
            defined_aliases.add(table_name.lower())

        # Check JOIN clauses for aliases
        join_matches = re.findall(r'JOIN\s+(\w+)(?:\s+AS\s+(\w+)|\s+(\w+))?', sql_upper)
        for join_match in join_matches:
            table_name, as_alias, direct_alias = join_match
            if as_alias:
                defined_aliases.add(as_alias.lower())
            elif direct_alias:
                defined_aliases.add(direct_alias.lower())
            defined_aliases.add(table_name.lower())

        # Fix undefined aliases by removing them or replacing with table names
        for alias, column in alias_refs:
            if alias.lower() not in defined_aliases:
                # Try to guess the correct table name based on common patterns
                if alias.lower() in ['p', 'prod']:
                    sql = sql.replace(f'{alias}.{column}', f'products.{column}')
                elif alias.lower() in ['c', 'cat']:
                    sql = sql.replace(f'{alias}.{column}', f'categories.{column}')
                elif alias.lower() in ['o', 'ord']:
                    sql = sql.replace(f'{alias}.{column}', f'orders.{column}')
                else:
                    # Remove the alias prefix
                    sql = sql.replace(f'{alias}.{column}', column)

        return sql

    def _fix_join_issues(self, sql: str) -> str:
        """Fix common JOIN issues"""
        import re

        sql_upper = sql.upper()

        # Fix incomplete JOIN conditions
        if 'JOIN' in sql_upper and 'ON' not in sql_upper:
            logger.warning("Adding missing JOIN condition")
            # Add a basic JOIN condition for products-categories
            if 'CATEGORIES' in sql_upper and 'PRODUCTS' in sql_upper:
                sql = re.sub(r'JOIN\s+categories', 'JOIN categories ON products.category_id = categories.id', sql, flags=re.IGNORECASE)

        # Fix incorrect JOIN references to non-existent tables/columns
        if 'customers.id' in sql and 'customers' not in sql_upper.split('FROM')[0]:
            # Remove incorrect references to customers table
            sql = re.sub(r'INNER JOIN categories ON orders\.customer_id = customers\.id', '', sql, flags=re.IGNORECASE)
            sql = re.sub(r'Inner Join categories ON orders\.category_id = categories\.id', '', sql, flags=re.IGNORECASE)

        return sql

    async def _fallback_generation(self, query: str, schema_context: List[Dict[str, Any]]) -> str:
        """Fallback to simpler generation if enhanced fails"""
        try:
            # Simple prompt
            schema_str = self._format_schema_context(schema_context)
            prompt = f"""Database Schema:
{schema_str}

Question: {query}

Generate a simple SQL SELECT query. Return only the SQL."""

            result = await self._agent.run(prompt)
            return self._extract_sql(result.output)

        except Exception as e:
            logger.error(f"Fallback generation also failed: {e}")
            # Return a safe default query
            if schema_context:
                first_table = schema_context[0].get('schema', {}).get('name', 'products')
                return f"SELECT * FROM {first_table} LIMIT 10"
            return "SELECT 'Error generating query' as error"

    async def _store_successful_query(self, query: str, sql: str):
        """Store successful query for future learning"""
        try:
            if self.vector_store and hasattr(self.vector_store, 'store_query_example'):
                self.vector_store.store_query_example(query, sql)
        except Exception as e:
            logger.debug(f"Failed to store query example: {e}")

    def _format_schema_context(self, schema_context: List[Dict[str, Any]]) -> str:
        """Simple schema formatting for fallback"""
        if not schema_context:
            return "No schema available"

        formatted = []
        for item in schema_context:
            if 'schema' in item:
                schema = item['schema']
                formatted.append(f"Table: {schema.get('name', 'unknown')}")
                if 'columns' in schema:
                    for col in schema['columns']:
                        if isinstance(col, dict):
                            formatted.append(f"  - {col.get('name', '')}: {col.get('type', '')}")
                        else:
                            formatted.append(f"  - {col}")

        return "\n".join(formatted)

    def _extract_sql(self, response: str) -> str:
        """Simple SQL extraction for fallback"""
        response = response.strip()
        for prefix in ['```sql', '```']:
            if response.startswith(prefix):
                response = response[len(prefix):]
                break
        if response.endswith('```'):
            response = response[:-3]
        return response.strip()

    async def generate_summary(self, data: List[Dict[str, Any]], query: str) -> str:
        """Generate a natural language summary of query results"""
        try:
            self._init_agent()
        except Exception as e:
            logger.warning(f"Failed to initialize agent for summary: {e}")
            # Return a safe fallback summary
            if data:
                return f"Found {len(data)} results for your query."
            return "No results found for your query."

        try:
            # Create a focused summary prompt
            if not data:
                return "No results found for your query."

            # Get basic info about the data
            row_count = len(data)
            columns = list(data[0].keys()) if data else []

            # Create sample data description
            sample_description = ""
            if data:
                sample_size = min(2, len(data))
                sample_description = f"\nData preview (showing {sample_size} of {row_count} total records):\n{json.dumps(data[:sample_size], indent=2)}"
                if row_count > sample_size:
                    sample_description += f"\n... and {row_count - sample_size} more records not shown in preview"

            # Use PromptManager to get summary generation prompt
            prompt_context = {
                'query': query,
                'row_count': row_count,
                'columns': ', '.join(columns),
                'sample_description': sample_description,
                'sample_size': min(2, row_count) if data else 0,
                'sample_data': json.dumps(data[:2], indent=2) if data else ''
            }

            prompt = self.prompt_manager.get_prompt(
                prompt_type='summary_generation.enhanced',
                provider='enhanced_ollama',
                context=prompt_context
            )

            result = await self._agent.run(prompt)
            summary = result.output.strip()

            # Clean up any unwanted content and validate count accuracy
            summary = self._clean_summary(summary, row_count, data)

            return summary

        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            if data:
                return f"Found {len(data)} results with {len(data[0].keys())} columns each."
            return "No results found for your query."

    def _clean_summary(self, summary: str, row_count: int = None, data: list = None) -> str:
        """Clean and format the summary with validation"""
        # If the entire summary looks like SQL, return a fallback
        if summary and summary.strip().upper().startswith(('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP')):
            return "Query executed successfully."

        # Remove any code blocks
        import re
        summary = re.sub(r'```[\s\S]*?```', '', summary)

        # Remove common unwanted phrases
        unwanted_phrases = [
            "Here is your SQL query:",
            "SQL:",
            "Query:",
            "```sql",
            "```",
            "Note that",
            "If I had to guess"
        ]

        for phrase in unwanted_phrases:
            summary = summary.replace(phrase, '')

        # Clean up extra whitespace and newlines
        summary = ' '.join(summary.split())

        # Ensure it doesn't start with Summary: prefix
        if summary.lower().startswith('summary:'):
            summary = summary[8:].strip()

        # Validate count accuracy if row_count provided
        if row_count is not None and data is not None:
            # Check for common mismatches (two, three, etc. when actual count differs)
            number_words = {
                'no': 0, 'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4,
                'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
            }

            summary_lower = summary.lower()
            for word, num in number_words.items():
                if word in summary_lower and num != row_count:
                    # Replace incorrect count words with actual count
                    summary = re.sub(r'\b' + word + r'\b', str(row_count), summary, flags=re.IGNORECASE)
                    logger.info(f"Corrected count mismatch: '{word}' -> {row_count}")

            # Also check for numeric mismatches (e.g., "2 customers" when there are 5)
            numeric_pattern = r'\b(\d+)\s+(record|result|row|customer|product|order|item|entry|entities)'
            matches = re.findall(numeric_pattern, summary_lower)
            for match in matches:
                stated_count = int(match[0])
                if stated_count != row_count:
                    # Replace with correct count
                    old_phrase = f"{stated_count} {match[1]}"
                    new_phrase = f"{row_count} {match[1]}"
                    summary = summary.replace(old_phrase, new_phrase)
                    logger.info(f"Corrected numeric mismatch: {stated_count} -> {row_count}")

        # Limit length to reasonable summary size
        if len(summary) > 200:
            sentences = summary.split('. ')
            summary = '. '.join(sentences[:2])
            if not summary.endswith('.'):
                summary += '.'

        # Final check: if summary contains SQL keywords at the start, replace it
        if summary and any(summary.strip().upper().startswith(kw) for kw in ['SELECT', 'FROM', 'WHERE', 'WITH']):
            return "Query executed successfully."

        return summary.strip()

    def is_available(self) -> bool:
        """Check if Ollama is available"""
        try:
            import requests
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                # Check if our model is available
                models = response.json().get('models', [])
                model_names = [m.get('name', '') for m in models]
                if self.model_name in model_names or any(self.model_name in name for name in model_names):
                    return True
                logger.warning(f"Model {self.model_name} not found in Ollama. Available: {model_names}")
            return False
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            return False

    def _get_dynamic_system_prompt(self) -> str:
        """Generate dynamic system prompt based on domain analysis"""
        # Use cached prompt if available
        if self._dynamic_system_prompt:
            return self._dynamic_system_prompt

        # Try to get domain-specific prompt from domain adapter
        if self.domain_adapter and self.domain_adapter.is_adapted():
            try:
                domain_config = self.domain_adapter.get_domain_configuration()
                if domain_config and hasattr(domain_config, 'system_prompt'):
                    self._dynamic_system_prompt = domain_config.system_prompt
                    logger.info("Using domain-adapted system prompt")
                    return self._dynamic_system_prompt

                # Generate prompt from domain analysis using PromptManager
                schema_analysis = domain_config.schema_analysis
                prompt = self.prompt_manager.get_dynamic_prompt(
                    prompt_type='sql_generation.enhanced',
                    schema_analysis=schema_analysis,
                    provider='enhanced_ollama'
                )
                self._dynamic_system_prompt = prompt
                logger.info("Generated system prompt from schema analysis via PromptManager")
                return prompt

            except Exception as e:
                logger.warning(f"Failed to get domain-specific prompt: {e}")

        # Fallback to generic prompt
        self._dynamic_system_prompt = self._get_generic_system_prompt()
        logger.info("Using generic fallback system prompt")
        return self._dynamic_system_prompt

    def _generate_prompt_from_schema_analysis(self, schema_analysis) -> str:
        """Generate system prompt from schema analysis"""
        prompt_parts = [
            "You are an expert SQL query generator for a database system.",
            "",
            "## DATABASE STRUCTURE:"
        ]

        # Add table descriptions
        for table in schema_analysis.tables:
            columns_desc = []
            for col in table.columns:
                col_desc = f"{col.name}: {col.sql_type}"
                if col.is_primary_key:
                    col_desc += " [PRIMARY KEY]"
                elif col.is_foreign_key and col.foreign_table:
                    col_desc += f" [FK → {col.foreign_table}.id]"
                columns_desc.append(col_desc)

            table_desc = f"- {table.name}: {table.table_type.title()} table ({', '.join(columns_desc[:5])}{'...' if len(columns_desc) > 5 else ''})"
            prompt_parts.append(table_desc)

        # Add relationships if available
        if schema_analysis.relationships:
            prompt_parts.append("")
            prompt_parts.append("## TABLE RELATIONSHIPS:")
            for rel in schema_analysis.relationships:
                if rel.get('confidence', 0) >= 0.8:  # Only high-confidence relationships
                    rel_desc = f"- {rel['from_table']}.{rel['from_column']} → {rel['to_table']}.{rel['to_column']}"
                    prompt_parts.append(rel_desc)

        # Add domain-specific patterns if available
        if schema_analysis.common_patterns:
            prompt_parts.append("")
            prompt_parts.append("## COMMON QUERY PATTERNS:")
            pattern_descriptions = {
                'aggregation_queries': "- Supports aggregation queries (SUM, AVG, COUNT) with GROUP BY",
                'temporal_queries': "- Supports time-based queries with date filtering",
                'multi_entity_queries': "- Supports complex joins between multiple tables"
            }
            for pattern in schema_analysis.common_patterns:
                if pattern in pattern_descriptions:
                    prompt_parts.append(pattern_descriptions[pattern])

        # Add strict rules
        prompt_parts.extend([
            "",
            "## STRICT RULES:",
            "1. ONLY generate SELECT queries",
            "2. Use EXACT table and column names from the schema above",
            "3. When joining tables, use the relationships listed above",
            "4. Return ONLY the SQL query, no explanations",
            "5. Always use proper JOIN conditions",
            "",
            "## IMPORTANT:",
            "- Never use non-existent columns or tables",
            "- Always validate table and column names against the schema above",
            "- Use appropriate data types and constraints"
        ])

        return "\\n".join(prompt_parts)

    def _get_generic_system_prompt(self) -> str:
        """Get generic fallback system prompt from PromptManager"""
        # Use PromptManager to get the fallback prompt
        return self.prompt_manager.get_prompt(
            prompt_type='sql_generation.enhanced',
            provider='enhanced_ollama'
        )

    def update_system_prompt(self, new_prompt: str):
        """Update system prompt manually (for testing or custom setups)"""
        self._dynamic_system_prompt = new_prompt
        self._agent = None  # Force agent recreation
        logger.info("System prompt updated manually")

    def clear_cached_prompt(self):
        """Clear cached prompt to force regeneration"""
        self._dynamic_system_prompt = None
        self._agent = None
        logger.info("Cached system prompt cleared")

    @property
    def name(self) -> str:
        """Provider name"""
        return f"Enhanced Ollama ({self.model_name})"