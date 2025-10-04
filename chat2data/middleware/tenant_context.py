"""Multi-tenant context middleware for Chat2Data"""

import logging
from typing import Optional, Callable
from functools import wraps
from contextvars import ContextVar

logger = logging.getLogger(__name__)

# Context variable to store current tenant ID
current_tenant: ContextVar[Optional[str]] = ContextVar('current_tenant', default=None)


class TenantContext:
    """
    Tenant context manager for multi-tenant applications

    Usage:
        with TenantContext(tenant_id="acme_corp"):
            # All operations within this context have tenant_id set
            result = chat2data.query("show campaigns")
    """

    def __init__(self, tenant_id: str):
        """
        Initialize tenant context

        Args:
            tenant_id: Unique tenant identifier
        """
        self.tenant_id = tenant_id
        self.token = None

    def __enter__(self):
        """Set tenant context on enter"""
        self.token = current_tenant.set(self.tenant_id)
        logger.debug(f"Tenant context set to: {self.tenant_id}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Reset tenant context on exit"""
        current_tenant.reset(self.token)
        logger.debug(f"Tenant context reset from: {self.tenant_id}")
        return False


def get_current_tenant() -> Optional[str]:
    """
    Get the current tenant ID from context

    Returns:
        Current tenant ID or None
    """
    return current_tenant.get()


def require_tenant(func):
    """
    Decorator to ensure tenant context is set

    Usage:
        @require_tenant
        async def process_query(query: str):
            tenant_id = get_current_tenant()
            # ... process with tenant_id
    """
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        tenant_id = get_current_tenant()
        if tenant_id is None:
            raise ValueError("Tenant context not set. Use TenantContext manager or set via middleware.")
        return await func(*args, **kwargs)

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        tenant_id = get_current_tenant()
        if tenant_id is None:
            raise ValueError("Tenant context not set. Use TenantContext manager or set via middleware.")
        return func(*args, **kwargs)

    # Return appropriate wrapper based on function type
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


class TenantAwareChat2Data:
    """
    Tenant-aware wrapper for Chat2Data that automatically uses tenant context

    This ensures all provider operations respect tenant isolation
    """

    def __init__(
        self,
        llm_provider,
        database_provider,
        vector_provider,
        tenant_id: Optional[str] = None
    ):
        """
        Initialize tenant-aware Chat2Data

        Args:
            llm_provider: LLM provider instance
            database_provider: Database provider instance
            vector_provider: Vector store provider instance
            tenant_id: Default tenant ID (can be overridden per request)
        """
        self.llm_provider = llm_provider
        self.database_provider = database_provider
        self.vector_provider = vector_provider
        self.default_tenant_id = tenant_id

        # Ensure providers support tenant context
        if hasattr(database_provider, 'tenant_id'):
            database_provider.tenant_id = tenant_id

        if hasattr(vector_provider, 'tenant_id'):
            vector_provider.tenant_id = tenant_id

    async def query(self, natural_language_query: str, tenant_id: Optional[str] = None) -> dict:
        """
        Execute a query with tenant context

        Args:
            natural_language_query: User's natural language query
            tenant_id: Tenant ID (uses default if not provided)

        Returns:
            Query results dictionary
        """
        tenant = tenant_id or self.default_tenant_id or get_current_tenant()

        if tenant is None:
            raise ValueError("No tenant ID provided and no tenant context set")

        with TenantContext(tenant):
            # Update provider tenant IDs if they support it
            if hasattr(self.database_provider, 'tenant_id'):
                self.database_provider.tenant_id = tenant

            if hasattr(self.vector_provider, 'tenant_id'):
                self.vector_provider.tenant_id = tenant

            # Perform vector search for relevant schema
            relevant_schemas = self.vector_provider.search_relevant_schema(
                natural_language_query,
                k=5
            )

            # Generate SQL using LLM
            sql = await self.llm_provider.generate_sql(
                natural_language_query,
                relevant_schemas
            )

            # Validate SQL
            is_valid, validation_message = self.database_provider.validate_sql(sql)
            if not is_valid:
                return {
                    'success': False,
                    'error': f"SQL validation failed: {validation_message}",
                    'tenant_id': tenant
                }

            # Execute query
            result = self.database_provider.execute_query(sql)

            # Store successful query for learning
            if result.success:
                self.vector_provider.store_query_example(natural_language_query, sql)

            # Generate summary
            if result.success and result.data:
                summary = await self.llm_provider.generate_summary(
                    result.data,
                    natural_language_query
                )
            else:
                summary = None

            return {
                'success': result.success,
                'sql': sql,
                'data': result.data,
                'columns': result.columns,
                'row_count': result.row_count,
                'summary': summary,
                'tenant_id': tenant,
                'error': result.error
            }


# FastAPI middleware for extracting tenant from JWT
class FastAPITenantMiddleware:
    """
    FastAPI middleware to extract tenant ID from JWT token and set context

    Usage:
        from fastapi import FastAPI

        app = FastAPI()
        app.add_middleware(FastAPITenantMiddleware)
    """

    def __init__(self, app, tenant_claim: str = "custom:tenant_id"):
        """
        Initialize middleware

        Args:
            app: FastAPI application
            tenant_claim: JWT claim containing tenant ID
        """
        self.app = app
        self.tenant_claim = tenant_claim

    async def __call__(self, scope, receive, send):
        """Process request and set tenant context"""
        if scope["type"] == "http":
            # Extract tenant from headers or JWT
            tenant_id = self._extract_tenant_id(scope)

            if tenant_id:
                # Set tenant context for this request
                token = current_tenant.set(tenant_id)
                try:
                    await self.app(scope, receive, send)
                finally:
                    current_tenant.reset(token)
            else:
                await self.app(scope, receive, send)
        else:
            await self.app(scope, receive, send)

    def _extract_tenant_id(self, scope) -> Optional[str]:
        """
        Extract tenant ID from request scope

        Priority:
        1. X-Tenant-ID header
        2. JWT claims
        3. None
        """
        headers = dict(scope.get("headers", []))

        # Check for X-Tenant-ID header
        tenant_header = headers.get(b"x-tenant-id")
        if tenant_header:
            return tenant_header.decode()

        # Check Authorization header for JWT
        auth_header = headers.get(b"authorization")
        if auth_header:
            try:
                token = auth_header.decode().replace("Bearer ", "")
                tenant_id = self._extract_tenant_from_jwt(token)
                if tenant_id:
                    return tenant_id
            except Exception as e:
                logger.warning(f"Failed to extract tenant from JWT: {e}")

        return None

    def _extract_tenant_from_jwt(self, token: str) -> Optional[str]:
        """
        Extract tenant ID from JWT token

        Args:
            token: JWT token string

        Returns:
            Tenant ID or None
        """
        try:
            import jwt

            # Decode without verification (verification should happen elsewhere)
            payload = jwt.decode(token, options={"verify_signature": False})
            return payload.get(self.tenant_claim)

        except Exception as e:
            logger.warning(f"Failed to decode JWT: {e}")
            return None


# Example usage in API endpoint
def create_tenant_aware_dependencies():
    """
    Create FastAPI dependencies for tenant-aware operations

    Usage:
        from fastapi import Depends

        @app.get("/query")
        async def query_endpoint(
            query: str,
            tenant_id: str = Depends(get_tenant_dependency)
        ):
            with TenantContext(tenant_id):
                # ... perform operations

    """
    def get_tenant_dependency() -> str:
        """FastAPI dependency to get current tenant"""
        tenant_id = get_current_tenant()
        if tenant_id is None:
            raise ValueError("No tenant context available")
        return tenant_id

    return get_tenant_dependency
