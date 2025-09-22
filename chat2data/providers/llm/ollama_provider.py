"""Ollama LLM provider for Chat2Data"""

import logging
from typing import Dict, List, Any, Optional
from ...core.base import LLMProvider
from ...config.central_config import get_config
from ...prompts import get_prompt_manager

logger = logging.getLogger(__name__)


class OllamaLLMProvider(LLMProvider):
    """Ollama LLM provider using PydanticAI"""

    def __init__(self, model_name: Optional[str] = None, base_url: Optional[str] = None):
        """Initialize Ollama provider with central configuration defaults"""
        config = get_config()
        self.model_name = model_name or config.llm.model_name
        self.base_url = base_url or config.llm.base_url
        self._agent = None
        self.prompt_manager = get_prompt_manager()  # Initialize centralized prompt manager

        logger.info(f"Initialized Ollama provider with model: {self.model_name}, base_url: {self.base_url}")

    def _init_agent(self):
        """Lazy initialization of PydanticAI agent"""
        if self._agent is None:
            try:
                import os
                from pydantic_ai import Agent

                # Set environment variables for OpenAI-compatible Ollama
                os.environ['OPENAI_BASE_URL'] = f"{self.base_url}/v1"
                os.environ['OPENAI_API_KEY'] = "ollama"  # Required but not used

                # Remove :latest suffix if present for model name
                model_name = self.model_name.replace(':latest', '') if self.model_name.endswith(':latest') else self.model_name

                # Get system prompt from PromptManager
                system_prompt = self.prompt_manager.get_prompt(
                    prompt_type='sql_generation.base',
                    provider='ollama'
                )

                self._agent = Agent(
                    f'openai:{model_name}',
                    system_prompt=system_prompt
                )
            except ImportError:
                logger.error("PydanticAI not available. Install with: pip install pydantic-ai")
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
            sql = self._extract_sql(result.output)

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

            row_count = len(data)
            sample_size = min(5, row_count)

            # Create sample description
            if row_count > 0:
                sample_description = f"""
Data preview (showing {sample_size} of {row_count} total records):
{json.dumps(data[:sample_size], indent=2)}"""
                if row_count > sample_size:
                    sample_description += f"\n... and {row_count - sample_size} more records not shown in preview"
            else:
                sample_description = "No data returned"

            # Use PromptManager to get summary generation prompt
            prompt_context = {
                'query': query,
                'row_count': row_count,
                'sample_description': sample_description,
                'sample_size': sample_size
            }

            prompt = self.prompt_manager.get_prompt(
                prompt_type='summary_generation.base',
                provider='ollama',
                context=prompt_context
            )

            result = await self._agent.run(prompt)
            summary = result.output

            # Validate and correct count mismatches
            summary = self._validate_summary(summary, row_count)
            return summary

        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return f"Query returned {len(data)} rows."

    def _validate_summary(self, summary: str, row_count: int) -> str:
        """Validate summary accuracy for row counts"""
        import re

        # Check for common number words that might be wrong
        number_words = {
            'no': 0, 'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4,
            'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
        }

        summary_lower = summary.lower()
        for word, num in number_words.items():
            if word in summary_lower and num != row_count:
                # Replace incorrect count words
                summary = re.sub(r'\b' + word + r'\b', str(row_count), summary, flags=re.IGNORECASE)
                logger.info(f"Corrected count mismatch in summary: '{word}' -> {row_count}")

        # Check for numeric mismatches
        numeric_pattern = r'\b(\d+)\s+(record|result|row|customer|product|order|item|entry|entit)'
        matches = re.findall(numeric_pattern, summary_lower)
        for match in matches:
            stated_count = int(match[0])
            if stated_count != row_count and stated_count <= 10:  # Only fix small counts
                old_phrase = f"{stated_count} {match[1]}"
                new_phrase = f"{row_count} {match[1]}"
                summary = summary.replace(old_phrase, new_phrase)
                logger.info(f"Corrected numeric mismatch: {stated_count} -> {row_count}")

        return summary

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