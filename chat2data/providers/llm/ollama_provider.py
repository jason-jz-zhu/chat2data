"""Ollama LLM provider for Chat2Data"""

import logging
from typing import Dict, List, Any
from ...core.base import LLMProvider

logger = logging.getLogger(__name__)


class OllamaLLMProvider(LLMProvider):
    """Ollama LLM provider using PydanticAI"""

    def __init__(self, model_name: str = 'llama3:latest', base_url: str = 'http://localhost:11434'):
        """Initialize Ollama provider"""
        self.model_name = model_name
        self.base_url = base_url
        self._agent = None
        self._model = None

    def _init_agent(self):
        """Lazy initialization of PydanticAI agent"""
        if self._agent is None:
            try:
                from pydantic_ai import Agent
                from pydantic_ai.models.ollama import OllamaModel

                self._model = OllamaModel(
                    model_name=self.model_name,
                    base_url=self.base_url
                )

                self._agent = Agent(
                    self._model,
                    system_prompt="""You are an expert SQL query generator. Your task is to convert natural language questions into valid SQL queries.

Rules:
1. Generate only SELECT queries (no INSERT, UPDATE, DELETE, DROP, etc.)
2. Use proper SQL syntax
3. Be precise and accurate based on the provided schema
4. If the query is ambiguous, make reasonable assumptions
5. Always use table and column names exactly as provided in the schema
6. Return ONLY the SQL query, no explanations or markdown

When given a schema context, use it to understand the database structure and relationships."""
                )
            except ImportError:
                logger.error("PydanticAI not available. Install with: pip install pydantic-ai[ollama]")
                raise

    async def generate_sql(self, query: str, schema_context: List[Dict[str, Any]]) -> str:
        """Generate SQL from natural language query"""
        self._init_agent()

        try:
            # Format schema context for the prompt
            schema_str = self._format_schema_context(schema_context)

            # Create prompt with schema context and user query
            prompt = f"""Database Schema:
{schema_str}

User Question: {query}

Generate a SQL query to answer this question. Return only the SQL query."""

            logger.info(f"Sending prompt to Ollama: {prompt[:200]}...")

            # Generate SQL using the agent
            result = await self._agent.run(prompt)

            # Extract SQL from response
            sql = self._extract_sql(result.data)

            logger.info(f"Generated SQL: {sql}")
            return sql

        except Exception as e:
            logger.error(f"Error generating SQL: {str(e)}")
            # Fallback to a simple SELECT query if generation fails
            return f"SELECT * FROM products LIMIT 10 -- Error: {str(e)}"

    async def generate_summary(self, data: List[Dict[str, Any]], query: str) -> str:
        """Generate a natural language summary of query results"""
        self._init_agent()

        try:
            import json

            prompt = f"""Based on this query: "{query}"

And these results (showing first 5 rows):
{json.dumps(data[:5], indent=2)}

Total rows: {len(data)}

Provide a brief, natural language summary of the results. Be concise and informative."""

            result = await self._agent.run(prompt)
            return result.data

        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return f"Query returned {len(data)} rows."

    def is_available(self) -> bool:
        """Check if Ollama is available"""
        try:
            import requests
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    @property
    def name(self) -> str:
        """Provider name"""
        return f"Ollama ({self.model_name})"

    def _format_schema_context(self, schema_context: List[Dict[str, Any]]) -> str:
        """Format schema context into a readable string for the LLM"""
        if not schema_context:
            return "No specific schema context available."

        formatted = []
        for item in schema_context:
            if 'schema' in item:
                schema = item['schema']
                table_info = f"Table: {schema.get('name', 'unknown')}\n"
                if 'columns' in schema:
                    table_info += "Columns:\n"
                    for col in schema['columns']:
                        if isinstance(col, dict):
                            table_info += f"  - {col.get('name', '')}: {col.get('type', 'unknown')}\n"
                        else:
                            table_info += f"  - {col}\n"
                formatted.append(table_info)
            elif 'table' in item:
                formatted.append(f"Table: {item['table']}")

        return "\n".join(formatted) if formatted else "No schema information available."

    def _extract_sql(self, response: str) -> str:
        """Extract SQL query from LLM response"""
        # Remove any markdown code blocks
        response = response.strip()
        if response.startswith('```sql'):
            response = response[6:]
        elif response.startswith('```'):
            response = response[3:]

        if response.endswith('```'):
            response = response[:-3]

        # Clean up the query
        response = response.strip()

        # Ensure it's a SELECT query
        if not response.upper().startswith('SELECT'):
            logger.warning(f"Generated query doesn't start with SELECT: {response}")
            # Try to find SELECT in the response
            import re
            select_match = re.search(r'(SELECT.*)', response, re.IGNORECASE | re.DOTALL)
            if select_match:
                response = select_match.group(1)

        return response