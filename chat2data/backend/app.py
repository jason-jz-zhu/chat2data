"""Flask application factory for Chat2Data backend"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import logging
import asyncio

from ..config.settings import Config
from ..core.chat2data import Chat2Data
from ..providers.llm.mock_provider import MockLLMProvider
from ..providers.llm.ollama_provider import OllamaLLMProvider
from ..providers.database.sqlite_provider import SQLiteDatabaseProvider
from ..providers.vector.memory_provider import MemoryVectorStoreProvider

logger = logging.getLogger(__name__)


class QueryRequest(BaseModel):
    query: str = Field(..., description="Natural language query")
    database: str = Field(default="default", description="Database to query")


class QueryResponse(BaseModel):
    success: bool
    query: str
    sql: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    error: Optional[str] = None


def create_chat2data_instance(config: Config) -> Chat2Data:
    """Create Chat2Data instance from configuration"""
    # Initialize LLM provider
    if config.llm.provider == "ollama":
        try:
            llm_provider = OllamaLLMProvider(
                model_name=config.llm.model_name,
                base_url=config.llm.base_url
            )
            if not llm_provider.is_available():
                logger.warning("Ollama not available, using mock provider")
                llm_provider = MockLLMProvider()
        except Exception as e:
            logger.warning(f"Failed to initialize Ollama: {e}, using mock provider")
            llm_provider = MockLLMProvider()
    else:
        llm_provider = MockLLMProvider()

    # Initialize database provider
    database_provider = SQLiteDatabaseProvider(config.database.path)

    # Initialize vector store provider
    vector_store_provider = MemoryVectorStoreProvider()

    return Chat2Data(
        llm_provider=llm_provider,
        database_provider=database_provider,
        vector_store_provider=vector_store_provider
    )


def create_app(config: Optional[Config] = None) -> Flask:
    """Create Flask application"""
    if config is None:
        config = Config.auto_detect()

    app = Flask(__name__)
    CORS(app)

    # Initialize Chat2Data instance
    chat2data = create_chat2data_instance(config)

    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint"""
        return jsonify({"status": "healthy", "service": "chat2data-backend"})

    @app.route('/api/query', methods=['POST'])
    def process_query():
        """Process natural language query and return SQL results"""
        try:
            data = request.json
            query_request = QueryRequest(**data)

            # Run async function in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                logger.info(f"Processing query: {query_request.query}")
                result = loop.run_until_complete(
                    chat2data.query(query_request.query)
                )

                return jsonify(QueryResponse(
                    success=result['success'],
                    query=result['query'],
                    sql=result.get('sql'),
                    result=result.get('result'),
                    summary=result.get('summary'),
                    error=result.get('error')
                ).model_dump())

            finally:
                loop.close()

        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            return jsonify(QueryResponse(
                success=False,
                query=data.get('query', ''),
                error=str(e)
            ).model_dump()), 500

    @app.route('/api/schema', methods=['GET'])
    def get_schema():
        """Get database schema information"""
        try:
            schema = chat2data.get_schema()
            return jsonify({
                "success": True,
                "schema": [table.model_dump() for table in schema]
            })
        except Exception as e:
            logger.error(f"Error fetching schema: {str(e)}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500

    @app.route('/api/schema/index', methods=['POST'])
    def index_schema():
        """Index database schema into vector store"""
        try:
            schema = chat2data.get_schema()
            if chat2data.vector_store:
                chat2data.vector_store.index_schema(schema)
                chat2data.force_reindex_schema()
            return jsonify({
                "success": True,
                "message": f"Indexed {len(schema)} tables"
            })
        except Exception as e:
            logger.error(f"Error indexing schema: {str(e)}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500

    @app.route('/api/suggestions', methods=['GET'])
    def get_suggestions():
        """Get query suggestions based on history"""
        try:
            query = request.args.get('q', '')
            suggestions = chat2data.get_similar_queries(query, k=5)
            return jsonify({
                "success": True,
                "suggestions": suggestions
            })
        except Exception as e:
            logger.error(f"Error getting suggestions: {str(e)}")
            return jsonify({
                "success": False,
                "suggestions": []
            })

    @app.route('/api/health', methods=['GET'])
    def api_health():
        """API health check with component status"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                health = loop.run_until_complete(chat2data.health_check())
                return jsonify({
                    "success": True,
                    "health": health
                })
            finally:
                loop.close()

        except Exception as e:
            logger.error(f"Error checking health: {str(e)}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500

    # Initialize schema on startup
    try:
        logger.info("Initializing schema index...")
        schema = chat2data.get_schema()
        if schema and chat2data.vector_store:
            chat2data.vector_store.index_schema(schema)
            logger.info(f"Indexed {len(schema)} tables")
    except Exception as e:
        logger.warning(f"Could not initialize schema: {e}")

    return app