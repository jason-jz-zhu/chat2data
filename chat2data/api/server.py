"""Production FastAPI server for Chat2Data on AWS"""

import logging
import os
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from ..middleware import (
    TenantAwareChat2Data,
    FastAPITenantMiddleware,
    get_current_tenant
)
from ..providers.llm import BedrockLLMProvider
from ..providers.database import AuroraPostgreSQLProvider
from ..providers.vector import OpenSearchVectorStoreProvider
from ..providers.llm.bedrock_provider import BedrockEmbeddingsProvider

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Chat2Data Marketing Chatbot API",
    description="Natural language to SQL API for marketing data insights",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add tenant middleware
app.add_middleware(FastAPITenantMiddleware)


# Request/Response models
class QueryRequest(BaseModel):
    query: str
    tenant_id: Optional[str] = None


class QueryResponse(BaseModel):
    success: bool
    sql: Optional[str] = None
    data: Optional[list] = None
    columns: Optional[list] = None
    row_count: int = 0
    summary: Optional[str] = None
    tenant_id: Optional[str] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    services: dict


class SchemaResponse(BaseModel):
    tables: list
    tenant_id: str


# Initialize providers (lazy loading)
_chat2data_instance = None


def get_chat2data() -> TenantAwareChat2Data:
    """Get or create Chat2Data instance with AWS providers"""
    global _chat2data_instance

    if _chat2data_instance is None:
        logger.info("Initializing Chat2Data with AWS providers...")

        # Initialize Bedrock LLM provider
        llm_provider = BedrockLLMProvider(
            model_id=os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0"),
            region_name=os.getenv("AWS_REGION", "us-east-1")
        )

        # Initialize Bedrock Embeddings provider
        embeddings_provider = BedrockEmbeddingsProvider(
            model_id=os.getenv("BEDROCK_EMBEDDINGS_MODEL", "amazon.titan-embed-text-v2:0"),
            region_name=os.getenv("AWS_REGION", "us-east-1")
        )

        # Initialize OpenSearch vector provider
        vector_provider = OpenSearchVectorStoreProvider(
            domain_endpoint=os.getenv("OPENSEARCH_ENDPOINT"),
            index_prefix=os.getenv("OPENSEARCH_INDEX_PREFIX", "chat2data"),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            embedding_provider=embeddings_provider
        )

        # Initialize Aurora PostgreSQL provider
        database_provider = AuroraPostgreSQLProvider(
            host=os.getenv("AURORA_HOST"),
            port=int(os.getenv("AURORA_PORT", "5432")),
            database=os.getenv("AURORA_DATABASE", "marketing"),
            user=os.getenv("AURORA_USER", "chat2data_admin"),
            password=os.getenv("AURORA_PASSWORD"),
            use_iam_auth=os.getenv("USE_IAM_AUTH", "false").lower() == "true",
            read_replica_host=os.getenv("AURORA_READ_REPLICA_HOST")
        )

        # Create tenant-aware Chat2Data instance
        _chat2data_instance = TenantAwareChat2Data(
            llm_provider=llm_provider,
            database_provider=database_provider,
            vector_provider=vector_provider
        )

        logger.info("Chat2Data initialized successfully")

    return _chat2data_instance


# API Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    chat2data = get_chat2data()

    services = {
        "llm": "unknown",
        "database": "unknown",
        "vector": "unknown"
    }

    try:
        services["llm"] = "healthy" if chat2data.llm_provider.is_available() else "unhealthy"
    except:
        services["llm"] = "unhealthy"

    try:
        services["database"] = "healthy" if chat2data.database_provider.is_connected() else "unhealthy"
    except:
        services["database"] = "unhealthy"

    try:
        services["vector"] = "healthy"  # OpenSearch doesn't have simple health check
    except:
        services["vector"] = "unhealthy"

    overall_status = "healthy" if all(s == "healthy" for s in services.values()) else "degraded"

    return HealthResponse(
        status=overall_status,
        version="1.0.0",
        services=services
    )


@app.post("/query", response_model=QueryResponse)
async def execute_query(
    request: QueryRequest,
    x_tenant_id: Optional[str] = Header(None)
):
    """
    Execute natural language query

    The tenant ID can be provided via:
    1. X-Tenant-ID header
    2. request.tenant_id field
    3. JWT token (via middleware)
    """
    try:
        chat2data = get_chat2data()

        # Determine tenant ID priority: header > request body > middleware context
        tenant_id = x_tenant_id or request.tenant_id or get_current_tenant()

        if not tenant_id:
            raise HTTPException(
                status_code=400,
                detail="Tenant ID required (via X-Tenant-ID header, request body, or JWT token)"
            )

        # Execute query
        result = await chat2data.query(
            natural_language_query=request.query,
            tenant_id=tenant_id
        )

        return QueryResponse(**result)

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/schema", response_model=SchemaResponse)
async def get_schema(x_tenant_id: Optional[str] = Header(None)):
    """Get database schema for tenant"""
    try:
        chat2data = get_chat2data()

        tenant_id = x_tenant_id or get_current_tenant()
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")

        # Update database provider tenant
        if hasattr(chat2data.database_provider, 'tenant_id'):
            chat2data.database_provider.tenant_id = tenant_id

        schema_info = chat2data.database_provider.get_schema()

        tables = []
        for table in schema_info:
            tables.append({
                "name": table.name,
                "columns": table.columns,
                "row_count": table.row_count,
                "description": table.description
            })

        return SchemaResponse(
            tables=tables,
            tenant_id=tenant_id
        )

    except Exception as e:
        logger.error(f"Error getting schema: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/index-schema")
async def index_schema(x_tenant_id: Optional[str] = Header(None)):
    """Index database schema into vector store"""
    try:
        chat2data = get_chat2data()

        tenant_id = x_tenant_id or get_current_tenant()
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")

        # Update providers with tenant
        if hasattr(chat2data.database_provider, 'tenant_id'):
            chat2data.database_provider.tenant_id = tenant_id
        if hasattr(chat2data.vector_provider, 'tenant_id'):
            chat2data.vector_provider.tenant_id = tenant_id

        # Get schema
        schema_info = chat2data.database_provider.get_schema()

        # Index into vector store
        success = chat2data.vector_provider.index_schema(schema_info)

        if success:
            return {"status": "success", "indexed_tables": len(schema_info)}
        else:
            raise HTTPException(status_code=500, detail="Failed to index schema")

    except Exception as e:
        logger.error(f"Error indexing schema: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Chat2Data Marketing Chatbot API",
        "version": "1.0.0",
        "documentation": "/docs"
    }


# Main entry point
def main():
    """Run the server"""
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")

    logger.info(f"Starting Chat2Data API server on {host}:{port}")

    uvicorn.run(
        "chat2data.api.server:app",
        host=host,
        port=port,
        reload=False,  # Set to True for development
        log_level="info"
    )


if __name__ == "__main__":
    main()
