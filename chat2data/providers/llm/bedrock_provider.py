"""AWS Bedrock LLM provider for Chat2Data"""

import json
import logging
from typing import Dict, List, Any, Optional
from ...core.base import LLMProvider
from ...config.central_config import get_config
from ...prompts import get_prompt_manager

logger = logging.getLogger(__name__)


class BedrockLLMProvider(LLMProvider):
    """AWS Bedrock LLM provider using Claude or other foundation models"""

    def __init__(
        self,
        model_id: Optional[str] = None,
        region_name: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None
    ):
        """
        Initialize Bedrock provider

        Args:
            model_id: Bedrock model ID (e.g., 'anthropic.claude-3-5-sonnet-20241022-v2:0')
            region_name: AWS region (e.g., 'us-east-1')
            aws_access_key_id: AWS access key (optional if using IAM role)
            aws_secret_access_key: AWS secret key (optional if using IAM role)
        """
        config = get_config()
        self.model_id = model_id or "anthropic.claude-3-5-sonnet-20241022-v2:0"
        self.region_name = region_name or "us-east-1"
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self._client = None
        self.prompt_manager = get_prompt_manager()

        logger.info(f"Initialized Bedrock provider with model: {self.model_id}, region: {self.region_name}")

    def _init_client(self):
        """Lazy initialization of Bedrock client"""
        if self._client is None:
            try:
                import boto3

                session_kwargs = {"region_name": self.region_name}
                if self.aws_access_key_id and self.aws_secret_access_key:
                    session_kwargs.update({
                        "aws_access_key_id": self.aws_access_key_id,
                        "aws_secret_access_key": self.aws_secret_access_key
                    })

                session = boto3.Session(**session_kwargs)
                self._client = session.client('bedrock-runtime')
                logger.info("Bedrock client initialized successfully")

            except ImportError:
                logger.error("boto3 not available. Install with: pip install boto3")
                raise
            except Exception as e:
                logger.error(f"Error initializing Bedrock client: {str(e)}")
                raise

    async def generate_sql(self, query: str, schema_context: List[Dict[str, Any]]) -> str:
        """Generate SQL from natural language query using Bedrock"""
        self._init_client()

        try:
            # Format schema context for the prompt
            schema_str = self._format_schema_context(schema_context)

            # Get system prompt from PromptManager
            system_prompt = self.prompt_manager.get_prompt(
                prompt_type='sql_generation.base',
                provider='bedrock'
            )

            # Create user message with schema context and query
            user_message = f"""Database Schema:
{schema_str}

User Question: {query}

Generate a SQL query to answer this question. Return only the SQL query without any explanations or markdown formatting."""

            # Prepare request body for Claude models
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "temperature": 0.1,  # Low temperature for more deterministic SQL generation
                "messages": [
                    {
                        "role": "user",
                        "content": user_message
                    }
                ],
                "system": system_prompt
            }

            logger.info(f"Sending request to Bedrock model: {self.model_id}")

            # Invoke Bedrock model
            response = self._client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )

            # Parse response
            response_body = json.loads(response['body'].read())

            # Extract SQL from Claude response
            if 'content' in response_body and len(response_body['content']) > 0:
                sql_text = response_body['content'][0]['text']
                sql = self._extract_sql(sql_text)
                logger.info(f"Generated SQL: {sql}")
                return sql
            else:
                logger.error(f"Unexpected response format: {response_body}")
                return "SELECT * FROM products LIMIT 10 -- Error: Unexpected response format"

        except Exception as e:
            logger.error(f"Error generating SQL with Bedrock: {str(e)}")
            return f"SELECT * FROM products LIMIT 10 -- Error: {str(e)}"

    async def generate_summary(self, data: List[Dict[str, Any]], query: str) -> str:
        """Generate a natural language summary of query results using Bedrock"""
        self._init_client()

        try:
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

            system_prompt = self.prompt_manager.get_prompt(
                prompt_type='summary_generation.base',
                provider='bedrock',
                context=prompt_context
            )

            # Create user message
            user_message = f"""Original query: {query}

{sample_description}

Please provide a concise, natural language summary of these results. Be accurate with the count of records ({row_count} total)."""

            # Prepare request body
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2048,
                "temperature": 0.3,
                "messages": [
                    {
                        "role": "user",
                        "content": user_message
                    }
                ],
                "system": system_prompt
            }

            # Invoke Bedrock model
            response = self._client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )

            # Parse response
            response_body = json.loads(response['body'].read())

            if 'content' in response_body and len(response_body['content']) > 0:
                summary = response_body['content'][0]['text']
                # Validate and correct count mismatches
                summary = self._validate_summary(summary, row_count)
                return summary
            else:
                return f"Query returned {row_count} rows."

        except Exception as e:
            logger.error(f"Error generating summary with Bedrock: {str(e)}")
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
        """Check if Bedrock is available"""
        try:
            self._init_client()
            # Try to list foundation models as a connectivity test
            response = self._client.list_foundation_models()
            return 'modelSummaries' in response
        except Exception as e:
            logger.warning(f"Bedrock availability check failed: {str(e)}")
            return False

    @property
    def name(self) -> str:
        """Provider name"""
        model_display = self.model_id.split('.')[-1] if '.' in self.model_id else self.model_id
        return f"AWS Bedrock ({model_display})"

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
                            col_name = col.get('name', '')
                            col_type = col.get('type', 'unknown')
                            col_desc = col.get('description', '')
                            table_info += f"  - {col_name}: {col_type}"
                            if col_desc:
                                table_info += f" ({col_desc})"
                            table_info += "\n"
                        else:
                            table_info += f"  - {col}\n"
                if 'description' in schema:
                    table_info += f"Description: {schema['description']}\n"
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


class BedrockEmbeddingsProvider:
    """AWS Bedrock Embeddings provider for vector operations"""

    def __init__(
        self,
        model_id: Optional[str] = None,
        region_name: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None
    ):
        """
        Initialize Bedrock Embeddings provider

        Args:
            model_id: Bedrock embeddings model ID (e.g., 'amazon.titan-embed-text-v2:0')
            region_name: AWS region
            aws_access_key_id: AWS access key (optional if using IAM role)
            aws_secret_access_key: AWS secret key (optional if using IAM role)
        """
        self.model_id = model_id or "amazon.titan-embed-text-v2:0"
        self.region_name = region_name or "us-east-1"
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self._client = None

        logger.info(f"Initialized Bedrock Embeddings provider with model: {self.model_id}")

    def _init_client(self):
        """Lazy initialization of Bedrock client"""
        if self._client is None:
            try:
                import boto3

                session_kwargs = {"region_name": self.region_name}
                if self.aws_access_key_id and self.aws_secret_access_key:
                    session_kwargs.update({
                        "aws_access_key_id": self.aws_access_key_id,
                        "aws_secret_access_key": self.aws_secret_access_key
                    })

                session = boto3.Session(**session_kwargs)
                self._client = session.client('bedrock-runtime')

            except ImportError:
                logger.error("boto3 not available. Install with: pip install boto3")
                raise

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors
        """
        self._init_client()

        embeddings = []
        for text in texts:
            try:
                request_body = {
                    "inputText": text
                }

                response = self._client.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps(request_body)
                )

                response_body = json.loads(response['body'].read())
                embedding = response_body.get('embedding', [])
                embeddings.append(embedding)

            except Exception as e:
                logger.error(f"Error generating embedding: {str(e)}")
                # Return zero vector on error
                embeddings.append([0.0] * 1536)  # Titan embeddings are 1536-dimensional

        return embeddings

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text

        Args:
            text: Text string to embed

        Returns:
            Embedding vector
        """
        embeddings = await self.generate_embeddings([text])
        return embeddings[0] if embeddings else []
