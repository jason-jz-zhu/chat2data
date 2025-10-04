"""Amazon OpenSearch vector store provider for production RAG implementation"""

import logging
import json
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from ...core.base import VectorStoreProvider, SchemaInfo

logger = logging.getLogger(__name__)


class OpenSearchVectorStoreProvider(VectorStoreProvider):
    """
    Amazon OpenSearch vector store provider with k-NN for semantic search

    Features:
    - Vector similarity search using k-NN algorithm (HNSW)
    - Hybrid search (vector + keyword)
    - Multi-tenant isolation
    - Schema and query pattern indexing
    - Production-ready with AWS integration
    """

    def __init__(
        self,
        domain_endpoint: str,
        index_prefix: str = "chat2data",
        region_name: str = "us-east-1",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        tenant_id: Optional[str] = None,
        embedding_provider=None
    ):
        """
        Initialize OpenSearch vector store

        Args:
            domain_endpoint: OpenSearch domain endpoint (e.g., 'search-domain.us-east-1.es.amazonaws.com')
            index_prefix: Prefix for index names (default: 'chat2data')
            region_name: AWS region
            aws_access_key_id: AWS access key (optional if using IAM role)
            aws_secret_access_key: AWS secret key (optional if using IAM role)
            tenant_id: Tenant ID for multi-tenant isolation
            embedding_provider: Provider for generating embeddings (e.g., BedrockEmbeddingsProvider)
        """
        self.domain_endpoint = domain_endpoint
        self.index_prefix = index_prefix
        self.region_name = region_name
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.tenant_id = tenant_id or "default"
        self.embedding_provider = embedding_provider
        self._client = None

        # Index names for different data types
        self.schema_index = f"{index_prefix}_{self.tenant_id}_schemas"
        self.query_index = f"{index_prefix}_{self.tenant_id}_queries"
        self.knowledge_index = f"{index_prefix}_{self.tenant_id}_knowledge"

        logger.info(f"Initialized OpenSearch vector store for tenant {self.tenant_id}")

    def _init_client(self):
        """Lazy initialization of OpenSearch client with AWS auth"""
        if self._client is None:
            try:
                from opensearchpy import OpenSearch, RequestsHttpConnection
                from requests_aws4auth import AWS4Auth
                import boto3

                # Create AWS auth
                if self.aws_access_key_id and self.aws_secret_access_key:
                    awsauth = AWS4Auth(
                        self.aws_access_key_id,
                        self.aws_secret_access_key,
                        self.region_name,
                        'es'
                    )
                else:
                    # Use boto3 session credentials (IAM role)
                    session = boto3.Session()
                    credentials = session.get_credentials()
                    awsauth = AWS4Auth(
                        credentials.access_key,
                        credentials.secret_key,
                        self.region_name,
                        'es',
                        session_token=credentials.token
                    )

                self._client = OpenSearch(
                    hosts=[{'host': self.domain_endpoint, 'port': 443}],
                    http_auth=awsauth,
                    use_ssl=True,
                    verify_certs=True,
                    connection_class=RequestsHttpConnection,
                    timeout=30
                )

                # Ensure indices exist
                self._ensure_indices_exist()

                logger.info("OpenSearch client initialized successfully")

            except ImportError as e:
                logger.error(f"Required packages not installed: {e}")
                logger.error("Install with: pip install opensearch-py requests-aws4auth boto3")
                raise
            except Exception as e:
                logger.error(f"Error initializing OpenSearch client: {str(e)}")
                raise

    def _ensure_indices_exist(self):
        """Create OpenSearch indices if they don't exist"""
        # Schema index configuration
        schema_index_body = {
            "settings": {
                "index": {
                    "knn": True,
                    "knn.algo_param.ef_search": 100
                }
            },
            "mappings": {
                "properties": {
                    "table_name": {"type": "keyword"},
                    "tenant_id": {"type": "keyword"},
                    "description": {"type": "text"},
                    "columns": {"type": "nested"},
                    "schema_text": {"type": "text"},
                    "embedding": {
                        "type": "knn_vector",
                        "dimension": 1536,  # Titan embeddings dimension
                        "method": {
                            "name": "hnsw",
                            "engine": "nmslib",
                            "space_type": "cosinesimil",
                            "parameters": {
                                "ef_construction": 128,
                                "m": 24
                            }
                        }
                    },
                    "row_count": {"type": "integer"},
                    "indexed_at": {"type": "date"}
                }
            }
        }

        # Query pattern index configuration
        query_index_body = {
            "settings": {
                "index": {
                    "knn": True
                }
            },
            "mappings": {
                "properties": {
                    "query_id": {"type": "keyword"},
                    "tenant_id": {"type": "keyword"},
                    "natural_language": {"type": "text"},
                    "sql": {"type": "text"},
                    "embedding": {
                        "type": "knn_vector",
                        "dimension": 1536,
                        "method": {
                            "name": "hnsw",
                            "engine": "nmslib",
                            "space_type": "cosinesimil",
                            "parameters": {
                                "ef_construction": 128,
                                "m": 24
                            }
                        }
                    },
                    "usage_count": {"type": "integer"},
                    "success_rate": {"type": "float"},
                    "created_at": {"type": "date"},
                    "last_used": {"type": "date"}
                }
            }
        }

        # Domain knowledge index configuration
        knowledge_index_body = {
            "settings": {
                "index": {
                    "knn": True
                }
            },
            "mappings": {
                "properties": {
                    "concept": {"type": "text"},
                    "tenant_id": {"type": "keyword"},
                    "aliases": {"type": "keyword"},
                    "description": {"type": "text"},
                    "calculation": {"type": "text"},
                    "embedding": {
                        "type": "knn_vector",
                        "dimension": 1536,
                        "method": {
                            "name": "hnsw",
                            "engine": "nmslib",
                            "space_type": "cosinesimil"
                        }
                    },
                    "related_tables": {"type": "keyword"}
                }
            }
        }

        # Create indices if they don't exist
        for index_name, index_body in [
            (self.schema_index, schema_index_body),
            (self.query_index, query_index_body),
            (self.knowledge_index, knowledge_index_body)
        ]:
            if not self._client.indices.exists(index=index_name):
                self._client.indices.create(index=index_name, body=index_body)
                logger.info(f"Created index: {index_name}")

    async def _get_embedding(self, text: str) -> List[float]:
        """Generate embedding using the configured embedding provider"""
        if self.embedding_provider is None:
            logger.error("No embedding provider configured")
            return [0.0] * 1536

        try:
            if hasattr(self.embedding_provider, 'generate_embedding'):
                embedding = await self.embedding_provider.generate_embedding(text)
                return embedding
            else:
                logger.error("Embedding provider doesn't support generate_embedding method")
                return [0.0] * 1536
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return [0.0] * 1536

    def search_relevant_schema(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for relevant schema using hybrid search (vector + keyword)

        Args:
            query: Natural language query
            k: Number of results to return

        Returns:
            List of relevant schema dictionaries with relevance scores
        """
        self._init_client()

        try:
            import asyncio

            # Generate query embedding
            query_embedding = asyncio.run(self._get_embedding(query))

            # Hybrid search query
            search_body = {
                "size": k,
                "query": {
                    "bool": {
                        "should": [
                            # Vector similarity search (70% weight)
                            {
                                "script_score": {
                                    "query": {
                                        "bool": {
                                            "filter": {
                                                "term": {"tenant_id": self.tenant_id}
                                            }
                                        }
                                    },
                                    "script": {
                                        "source": "knn_score",
                                        "lang": "knn",
                                        "params": {
                                            "field": "embedding",
                                            "query_value": query_embedding,
                                            "space_type": "cosinesimil"
                                        }
                                    },
                                    "boost": 0.7
                                }
                            },
                            # Keyword search (30% weight)
                            {
                                "multi_match": {
                                    "query": query,
                                    "fields": ["table_name^3", "schema_text^2", "description"],
                                    "boost": 0.3
                                }
                            }
                        ],
                        "filter": {
                            "term": {"tenant_id": self.tenant_id}
                        }
                    }
                }
            }

            response = self._client.search(index=self.schema_index, body=search_body)

            results = []
            for hit in response['hits']['hits']:
                source = hit['_source']
                results.append({
                    'schema': {
                        'name': source['table_name'],
                        'columns': source.get('columns', []),
                        'description': source.get('description', ''),
                        'row_count': source.get('row_count', 0)
                    },
                    'relevance_score': hit['_score'],
                    'table_name': source['table_name']
                })

            logger.info(f"Found {len(results)} relevant schemas for query: {query}")
            return results

        except Exception as e:
            logger.error(f"Error searching schemas: {e}")
            return []

    def index_schema(self, schema: List[SchemaInfo]) -> bool:
        """
        Index schema information with vector embeddings

        Args:
            schema: List of SchemaInfo objects to index

        Returns:
            True if successful, False otherwise
        """
        self._init_client()

        try:
            import asyncio

            for schema_info in schema:
                # Create text representation for embedding
                schema_text = self._create_schema_text(schema_info)

                # Generate embedding
                embedding = asyncio.run(self._get_embedding(schema_text))

                # Prepare document
                doc = {
                    "table_name": schema_info.name,
                    "tenant_id": self.tenant_id,
                    "description": schema_info.description or f"Table {schema_info.name}",
                    "columns": [col if isinstance(col, dict) else {"name": col} for col in schema_info.columns],
                    "schema_text": schema_text,
                    "embedding": embedding,
                    "row_count": schema_info.row_count or 0,
                    "indexed_at": "now"
                }

                # Index or update document
                doc_id = hashlib.md5(f"{self.tenant_id}_{schema_info.name}".encode()).hexdigest()
                self._client.index(
                    index=self.schema_index,
                    id=doc_id,
                    body=doc,
                    refresh=True
                )

            logger.info(f"Successfully indexed {len(schema)} schemas")
            return True

        except Exception as e:
            logger.error(f"Error indexing schema: {e}")
            return False

    def _create_schema_text(self, schema_info: SchemaInfo) -> str:
        """Create a text representation of schema for embedding"""
        text_parts = [
            f"Table: {schema_info.name}",
        ]

        if schema_info.description:
            text_parts.append(f"Description: {schema_info.description}")

        if schema_info.row_count:
            text_parts.append(f"Rows: {schema_info.row_count}")

        # Add column information
        for column in schema_info.columns:
            if isinstance(column, dict):
                col_name = column.get('name', 'Unknown')
                col_type = column.get('type', 'Unknown')
                col_text = f"Column {col_name} ({col_type})"

                if column.get('description'):
                    col_text += f": {column['description']}"
                if column.get('primary_key'):
                    col_text += " [PRIMARY KEY]"
                if column.get('foreign_key'):
                    col_text += f" [REFERENCES {column['foreign_key']}]"

                text_parts.append(col_text)
            else:
                text_parts.append(f"Column: {column}")

        return " | ".join(text_parts)

    def store_query_example(self, query: str, sql: str) -> bool:
        """
        Store successful query examples with embeddings

        Args:
            query: Natural language query
            sql: Generated SQL

        Returns:
            True if successful, False otherwise
        """
        self._init_client()

        try:
            import asyncio

            # Create combined text for embedding
            combined_text = f"Query: {query} SQL: {sql}"
            embedding = asyncio.run(self._get_embedding(combined_text))

            # Generate unique query ID
            query_id = hashlib.md5(f"{self.tenant_id}_{query}_{sql}".encode()).hexdigest()

            # Check if query already exists
            try:
                existing = self._client.get(index=self.query_index, id=query_id)
                usage_count = existing['_source'].get('usage_count', 0) + 1
                success_rate = existing['_source'].get('success_rate', 1.0)
            except:
                usage_count = 1
                success_rate = 1.0

            # Prepare document
            doc = {
                "query_id": query_id,
                "tenant_id": self.tenant_id,
                "natural_language": query,
                "sql": sql,
                "embedding": embedding,
                "usage_count": usage_count,
                "success_rate": success_rate,
                "created_at": "now",
                "last_used": "now"
            }

            # Index or update document
            self._client.index(
                index=self.query_index,
                id=query_id,
                body=doc,
                refresh=True
            )

            logger.info(f"Stored query example: {query[:50]}...")
            return True

        except Exception as e:
            logger.error(f"Error storing query example: {e}")
            return False

    def get_similar_queries(self, query: str, k: int = 5) -> List[Tuple[str, str, float]]:
        """
        Get similar queries from history using semantic similarity

        Args:
            query: Natural language query
            k: Number of results to return

        Returns:
            List of (query, sql, similarity_score) tuples
        """
        self._init_client()

        try:
            import asyncio

            # Generate query embedding
            query_embedding = asyncio.run(self._get_embedding(query))

            # k-NN search
            search_body = {
                "size": k,
                "query": {
                    "script_score": {
                        "query": {
                            "bool": {
                                "filter": {
                                    "term": {"tenant_id": self.tenant_id}
                                }
                            }
                        },
                        "script": {
                            "source": "knn_score",
                            "lang": "knn",
                            "params": {
                                "field": "embedding",
                                "query_value": query_embedding,
                                "space_type": "cosinesimil"
                            }
                        }
                    }
                }
            }

            response = self._client.search(index=self.query_index, body=search_body)

            results = []
            for hit in response['hits']['hits']:
                source = hit['_source']
                results.append((
                    source['natural_language'],
                    source['sql'],
                    hit['_score']
                ))

            logger.info(f"Found {len(results)} similar queries")
            return results

        except Exception as e:
            logger.error(f"Error searching similar queries: {e}")
            return []

    def index_domain_knowledge(self, knowledge_items: List[Dict[str, Any]]) -> bool:
        """
        Index domain knowledge (e.g., marketing metrics, business terms)

        Args:
            knowledge_items: List of knowledge items with concept, description, etc.

        Returns:
            True if successful, False otherwise
        """
        self._init_client()

        try:
            import asyncio

            for item in knowledge_items:
                # Create text for embedding
                text = f"{item['concept']} {item.get('description', '')} {' '.join(item.get('aliases', []))}"
                embedding = asyncio.run(self._get_embedding(text))

                # Prepare document
                doc = {
                    "concept": item['concept'],
                    "tenant_id": self.tenant_id,
                    "aliases": item.get('aliases', []),
                    "description": item.get('description', ''),
                    "calculation": item.get('calculation', ''),
                    "embedding": embedding,
                    "related_tables": item.get('related_tables', [])
                }

                # Index document
                doc_id = hashlib.md5(f"{self.tenant_id}_{item['concept']}".encode()).hexdigest()
                self._client.index(
                    index=self.knowledge_index,
                    id=doc_id,
                    body=doc,
                    refresh=True
                )

            logger.info(f"Indexed {len(knowledge_items)} knowledge items")
            return True

        except Exception as e:
            logger.error(f"Error indexing domain knowledge: {e}")
            return False

    def search_domain_knowledge(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """
        Search domain knowledge base

        Args:
            query: Search query
            k: Number of results to return

        Returns:
            List of relevant knowledge items
        """
        self._init_client()

        try:
            import asyncio

            query_embedding = asyncio.run(self._get_embedding(query))

            search_body = {
                "size": k,
                "query": {
                    "script_score": {
                        "query": {
                            "bool": {
                                "filter": {
                                    "term": {"tenant_id": self.tenant_id}
                                }
                            }
                        },
                        "script": {
                            "source": "knn_score",
                            "lang": "knn",
                            "params": {
                                "field": "embedding",
                                "query_value": query_embedding,
                                "space_type": "cosinesimil"
                            }
                        }
                    }
                }
            }

            response = self._client.search(index=self.knowledge_index, body=search_body)

            results = []
            for hit in response['hits']['hits']:
                results.append(hit['_source'])

            return results

        except Exception as e:
            logger.error(f"Error searching domain knowledge: {e}")
            return []

    @property
    def name(self) -> str:
        """Provider name"""
        return f"Amazon OpenSearch (tenant: {self.tenant_id})"
