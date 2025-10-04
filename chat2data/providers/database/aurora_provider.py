"""AWS Aurora PostgreSQL database provider for Chat2Data"""

import logging
import re
from typing import List, Tuple, Dict, Any, Optional
from ...core.base import DatabaseProvider, QueryResult, SchemaInfo

logger = logging.getLogger(__name__)


class AuroraPostgreSQLProvider(DatabaseProvider):
    """
    AWS Aurora PostgreSQL database provider with multi-tenant support

    Features:
    - Connection pooling
    - Row-level security (RLS) for tenant isolation
    - Read replica support
    - Automatic failover
    - Query cost estimation
    - Production-ready error handling
    """

    def __init__(
        self,
        host: str,
        port: int = 5432,
        database: str = "postgres",
        user: str = "postgres",
        password: Optional[str] = None,
        tenant_id: Optional[str] = None,
        use_iam_auth: bool = False,
        read_replica_host: Optional[str] = None,
        pool_size: int = 10,
        max_overflow: int = 20,
        pool_timeout: int = 30
    ):
        """
        Initialize Aurora PostgreSQL provider

        Args:
            host: Aurora cluster endpoint
            port: Database port (default: 5432)
            database: Database name
            user: Database user
            password: Database password (not needed if use_iam_auth=True)
            tenant_id: Tenant ID for multi-tenant isolation
            use_iam_auth: Use AWS IAM authentication
            read_replica_host: Read replica endpoint for SELECT queries
            pool_size: Connection pool size
            max_overflow: Maximum overflow connections
            pool_timeout: Pool checkout timeout
        """
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.tenant_id = tenant_id or "default"
        self.use_iam_auth = use_iam_auth
        self.read_replica_host = read_replica_host
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout

        self._engine = None
        self._read_engine = None

        logger.info(f"Initialized Aurora PostgreSQL provider for tenant: {self.tenant_id}")

    def _get_iam_token(self, host: str) -> str:
        """Generate IAM authentication token"""
        try:
            import boto3

            client = boto3.client('rds', region_name=self._get_region_from_endpoint(host))
            token = client.generate_db_auth_token(
                DBHostname=host,
                Port=self.port,
                DBUsername=self.user
            )
            return token
        except Exception as e:
            logger.error(f"Error generating IAM token: {e}")
            raise

    def _get_region_from_endpoint(self, endpoint: str) -> str:
        """Extract AWS region from Aurora endpoint"""
        # Aurora endpoint format: cluster-name.cluster-xxxxx.region.rds.amazonaws.com
        parts = endpoint.split('.')
        if len(parts) >= 3:
            return parts[-3]
        return "us-east-1"  # default

    def _init_engine(self):
        """Lazy initialization of SQLAlchemy engine with connection pooling"""
        if self._engine is None:
            try:
                from sqlalchemy import create_engine
                from sqlalchemy.pool import QueuePool

                # Build connection string
                password = self._get_iam_token(self.host) if self.use_iam_auth else self.password
                connection_string = f"postgresql://{self.user}:{password}@{self.host}:{self.port}/{self.database}"

                # Create engine with connection pooling
                self._engine = create_engine(
                    connection_string,
                    poolclass=QueuePool,
                    pool_size=self.pool_size,
                    max_overflow=self.max_overflow,
                    pool_timeout=self.pool_timeout,
                    pool_pre_ping=True,  # Verify connections before using
                    echo=False
                )

                # Create read replica engine if configured
                if self.read_replica_host:
                    password_replica = self._get_iam_token(self.read_replica_host) if self.use_iam_auth else self.password
                    read_connection_string = f"postgresql://{self.user}:{password_replica}@{self.read_replica_host}:{self.port}/{self.database}"

                    self._read_engine = create_engine(
                        read_connection_string,
                        poolclass=QueuePool,
                        pool_size=self.pool_size // 2,  # Smaller pool for read replica
                        max_overflow=self.max_overflow // 2,
                        pool_timeout=self.pool_timeout,
                        pool_pre_ping=True,
                        echo=False
                    )

                logger.info("Aurora PostgreSQL engine initialized successfully")

            except ImportError:
                logger.error("SQLAlchemy not available. Install with: pip install sqlalchemy psycopg2-binary")
                raise
            except Exception as e:
                logger.error(f"Error initializing database engine: {e}")
                raise

    def _get_engine(self, read_only: bool = False):
        """Get appropriate engine based on query type"""
        self._init_engine()

        # Use read replica for SELECT queries if available
        if read_only and self._read_engine:
            return self._read_engine
        return self._engine

    def _set_tenant_context(self, connection):
        """Set tenant context for row-level security"""
        try:
            connection.execute(f"SET app.current_tenant = '{self.tenant_id}'")
        except Exception as e:
            logger.warning(f"Could not set tenant context: {e}")

    def execute_query(self, sql: str) -> QueryResult:
        """
        Execute SQL query and return results

        Args:
            sql: SQL query string

        Returns:
            QueryResult with data or error
        """
        try:
            from sqlalchemy import text

            # Determine if this is a read-only query
            is_read_only = sql.strip().upper().startswith('SELECT')
            engine = self._get_engine(read_only=is_read_only)

            with engine.connect() as connection:
                # Set tenant context for RLS
                self._set_tenant_context(connection)

                # Execute query
                result = connection.execute(text(sql))

                # Fetch results
                if result.returns_rows:
                    rows = result.fetchall()
                    columns = list(result.keys())

                    # Convert to list of dictionaries
                    data = [dict(zip(columns, row)) for row in rows]

                    return QueryResult(
                        success=True,
                        data=data,
                        columns=columns,
                        row_count=len(data)
                    )
                else:
                    return QueryResult(
                        success=True,
                        row_count=0
                    )

        except Exception as e:
            logger.error(f"Error executing query: {e}")
            return QueryResult(
                success=False,
                error=str(e)
            )

    def get_schema(self) -> List[SchemaInfo]:
        """
        Get database schema information

        Returns:
            List of SchemaInfo objects
        """
        try:
            from sqlalchemy import text

            engine = self._get_engine(read_only=True)

            with engine.connect() as connection:
                # Set tenant context
                self._set_tenant_context(connection)

                # Get all tables in public schema (or tenant-specific schema)
                tables_query = text("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """)

                tables_result = connection.execute(tables_query)
                tables = [row[0] for row in tables_result.fetchall()]

                schema_info = []
                for table_name in tables:
                    # Get column information
                    columns_query = text("""
                        SELECT
                            column_name,
                            data_type,
                            is_nullable,
                            column_default,
                            character_maximum_length
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                        AND table_name = :table_name
                        ORDER BY ordinal_position
                    """)

                    columns_result = connection.execute(columns_query, {"table_name": table_name})
                    columns_data = columns_result.fetchall()

                    # Get primary key information
                    pk_query = text("""
                        SELECT column_name
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu
                            ON tc.constraint_name = kcu.constraint_name
                            AND tc.table_schema = kcu.table_schema
                        WHERE tc.constraint_type = 'PRIMARY KEY'
                        AND tc.table_schema = 'public'
                        AND tc.table_name = :table_name
                    """)

                    pk_result = connection.execute(pk_query, {"table_name": table_name})
                    primary_keys = {row[0] for row in pk_result.fetchall()}

                    # Get foreign key information
                    fk_query = text("""
                        SELECT
                            kcu.column_name,
                            ccu.table_name AS foreign_table_name,
                            ccu.column_name AS foreign_column_name
                        FROM information_schema.table_constraints AS tc
                        JOIN information_schema.key_column_usage AS kcu
                            ON tc.constraint_name = kcu.constraint_name
                            AND tc.table_schema = kcu.table_schema
                        JOIN information_schema.constraint_column_usage AS ccu
                            ON ccu.constraint_name = tc.constraint_name
                            AND ccu.table_schema = tc.table_schema
                        WHERE tc.constraint_type = 'FOREIGN KEY'
                        AND tc.table_schema = 'public'
                        AND tc.table_name = :table_name
                    """)

                    fk_result = connection.execute(fk_query, {"table_name": table_name})
                    foreign_keys = {}
                    for row in fk_result.fetchall():
                        foreign_keys[row[0]] = f"{row[1]}.{row[2]}"

                    # Build column list
                    columns = []
                    for col in columns_data:
                        col_name = col[0]
                        column_info = {
                            'name': col_name,
                            'type': col[1],
                            'nullable': col[2] == 'YES',
                            'primary_key': col_name in primary_keys
                        }

                        if col_name in foreign_keys:
                            column_info['foreign_key'] = foreign_keys[col_name]

                        if col[3]:  # default value
                            column_info['default'] = col[3]

                        if col[4]:  # character max length
                            column_info['max_length'] = col[4]

                        columns.append(column_info)

                    # Get row count (with tenant filter if RLS is enabled)
                    try:
                        count_query = text(f"SELECT COUNT(*) FROM {table_name}")
                        count_result = connection.execute(count_query)
                        row_count = count_result.fetchone()[0]
                    except:
                        row_count = 0

                    schema_info.append(SchemaInfo(
                        name=table_name,
                        columns=columns,
                        row_count=row_count
                    ))

            return schema_info

        except Exception as e:
            logger.error(f"Error getting schema: {e}")
            return []

    def validate_sql(self, sql: str) -> Tuple[bool, str]:
        """
        Validate SQL for safety and syntax

        Args:
            sql: SQL query string

        Returns:
            Tuple of (is_valid, message)
        """
        sql_stripped = sql.strip()
        sql_upper = sql_stripped.upper()

        # Check for dangerous operations
        dangerous_keywords = [
            'DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 'CREATE',
            'TRUNCATE', 'REPLACE', 'GRANT', 'REVOKE'
        ]

        # Use word boundaries to match whole words only
        for keyword in dangerous_keywords:
            if re.search(r'\b' + keyword + r'\b', sql_upper):
                return False, f"Forbidden SQL operation: {keyword}"

        # Prevent multiple statements
        if ';' in sql_stripped and not sql_stripped.endswith(';'):
            return False, "Multiple SQL statements not allowed"

        # Must be a SELECT statement
        if not sql_upper.startswith('SELECT'):
            return False, "Only SELECT queries are allowed"

        # Check for potential SQL injection patterns
        injection_patterns = [
            r'--',           # SQL comments
            r'/\*',          # Multi-line comments
            r'xp_cmdshell',  # Command execution
            r'sp_',          # System stored procedures
            r'pg_',          # PostgreSQL system functions (selective)
        ]

        for pattern in injection_patterns:
            if re.search(pattern, sql_upper):
                return False, f"Potentially dangerous pattern detected: {pattern}"

        # Basic syntax validation
        if sql_stripped.count('(') != sql_stripped.count(')'):
            return False, "Mismatched parentheses"

        # Estimate query cost and warn if expensive
        cost_estimate = self._estimate_query_cost(sql_stripped)
        if cost_estimate > 1000000:  # Arbitrary threshold
            return False, f"Query appears too expensive (estimated cost: {cost_estimate})"

        return True, "Valid SQL"

    def _estimate_query_cost(self, sql: str) -> int:
        """
        Estimate query cost based on heuristics

        Args:
            sql: SQL query string

        Returns:
            Estimated cost (higher = more expensive)
        """
        cost = 0

        # Count JOINs (each JOIN increases cost)
        cost += sql.upper().count('JOIN') * 100

        # Count subqueries
        cost += sql.count('SELECT') * 50

        # Cartesian products (JOIN without ON)
        if 'JOIN' in sql.upper() and 'ON' not in sql.upper():
            cost += 10000

        # No WHERE clause on large tables
        if 'WHERE' not in sql.upper():
            cost += 500

        # LIKE with leading wildcard
        if re.search(r"LIKE\s+'%", sql.upper()):
            cost += 200

        return cost

    def is_connected(self) -> bool:
        """
        Check if database is connected

        Returns:
            True if connected, False otherwise
        """
        try:
            from sqlalchemy import text

            engine = self._get_engine(read_only=True)
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Connection check failed: {e}")
            return False

    def get_table_relationships(self) -> List[Dict[str, Any]]:
        """
        Get table relationships based on foreign keys

        Returns:
            List of relationship dictionaries
        """
        try:
            from sqlalchemy import text

            engine = self._get_engine(read_only=True)

            with engine.connect() as connection:
                query = text("""
                    SELECT
                        tc.table_name AS from_table,
                        kcu.column_name AS from_column,
                        ccu.table_name AS to_table,
                        ccu.column_name AS to_column
                    FROM information_schema.table_constraints AS tc
                    JOIN information_schema.key_column_usage AS kcu
                        ON tc.constraint_name = kcu.constraint_name
                        AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage AS ccu
                        ON ccu.constraint_name = tc.constraint_name
                        AND ccu.table_schema = tc.table_schema
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                    AND tc.table_schema = 'public'
                """)

                result = connection.execute(query)
                relationships = []

                for row in result.fetchall():
                    relationships.append({
                        'from_table': row[0],
                        'from_column': row[1],
                        'to_table': row[2],
                        'to_column': row[3],
                        'relationship_type': 'foreign_key'
                    })

                return relationships

        except Exception as e:
            logger.error(f"Error getting table relationships: {e}")
            return []

    def setup_row_level_security(self) -> bool:
        """
        Setup row-level security for multi-tenant isolation

        This should be run once during deployment to enable RLS on tables

        Returns:
            True if successful, False otherwise
        """
        try:
            from sqlalchemy import text

            engine = self._get_engine(read_only=False)

            with engine.begin() as connection:
                # Get all tables
                schema_info = self.get_schema()

                for table in schema_info:
                    table_name = table.name

                    # Check if table has tenant_id column
                    has_tenant_id = any(col['name'] == 'tenant_id' for col in table.columns)

                    if has_tenant_id:
                        # Enable RLS
                        connection.execute(text(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY"))

                        # Create policy for tenant isolation
                        policy_name = f"{table_name}_tenant_isolation"

                        # Drop existing policy if it exists
                        connection.execute(text(f"DROP POLICY IF EXISTS {policy_name} ON {table_name}"))

                        # Create new policy
                        connection.execute(text(f"""
                            CREATE POLICY {policy_name} ON {table_name}
                            USING (tenant_id = current_setting('app.current_tenant')::uuid)
                        """))

                        logger.info(f"Enabled RLS on table: {table_name}")

            return True

        except Exception as e:
            logger.error(f"Error setting up RLS: {e}")
            return False

    @property
    def name(self) -> str:
        """Provider name"""
        return f"Aurora PostgreSQL ({self.host}, tenant: {self.tenant_id})"
