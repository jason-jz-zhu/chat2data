"""SQLite database provider for Chat2Data"""

import sqlite3
import logging
import os
from typing import List, Tuple, Dict, Any
from ...core.base import DatabaseProvider, QueryResult, SchemaInfo

logger = logging.getLogger(__name__)


class SQLiteDatabaseProvider(DatabaseProvider):
    """SQLite database provider implementation"""

    def __init__(self, database_path: str = ":memory:"):
        """
        Initialize SQLite provider

        Args:
            database_path: Path to SQLite database file or ":memory:" for in-memory DB
        """
        self.database_path = database_path
        self._ensure_database_exists()

    def _ensure_database_exists(self):
        """Ensure database file exists and create sample data if needed"""
        if self.database_path == ":memory:":
            return

        # Create directory if it doesn't exist
        db_dir = os.path.dirname(self.database_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        # Create sample data if database doesn't exist
        if not os.path.exists(self.database_path):
            self._create_sample_database()

    def _create_sample_database(self):
        """Create a sample database with demo data"""
        logger.info(f"Creating sample database at {self.database_path}")

        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()

        try:
            # Create sample tables
            cursor.execute("""
                CREATE TABLE categories (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE products (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    category_id INTEGER,
                    price DECIMAL(10,2),
                    stock_quantity INTEGER DEFAULT 0,
                    description TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (category_id) REFERENCES categories (id)
                )
            """)

            cursor.execute("""
                CREATE TABLE customers (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE,
                    phone TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE orders (
                    id INTEGER PRIMARY KEY,
                    customer_id INTEGER,
                    total_amount DECIMAL(10,2),
                    status TEXT DEFAULT 'pending',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (customer_id) REFERENCES customers (id)
                )
            """)

            cursor.execute("""
                CREATE TABLE order_items (
                    id INTEGER PRIMARY KEY,
                    order_id INTEGER,
                    product_id INTEGER,
                    quantity INTEGER,
                    price DECIMAL(10,2),
                    FOREIGN KEY (order_id) REFERENCES orders (id),
                    FOREIGN KEY (product_id) REFERENCES products (id)
                )
            """)

            # Insert sample data
            categories_data = [
                (1, 'Electronics', 'Electronic devices and gadgets'),
                (2, 'Clothing', 'Apparel and fashion items'),
                (3, 'Books', 'Books and educational materials'),
                (4, 'Home & Garden', 'Home improvement and garden supplies'),
            ]
            cursor.executemany("INSERT INTO categories VALUES (?, ?, ?)", categories_data)

            products_data = [
                (1, 'Laptop Computer', 1, 999.99, 15, 'High-performance laptop'),
                (2, 'Smartphone', 1, 699.99, 25, 'Latest model smartphone'),
                (3, 'T-Shirt', 2, 29.99, 50, 'Cotton t-shirt'),
                (4, 'Jeans', 2, 79.99, 30, 'Classic blue jeans'),
                (5, 'Python Programming Book', 3, 49.99, 20, 'Learn Python programming'),
                (6, 'Garden Tools Set', 4, 89.99, 10, 'Complete garden tools'),
                (7, 'Wireless Headphones', 1, 199.99, 18, 'Noise-cancelling headphones'),
                (8, 'Coffee Maker', 4, 129.99, 12, 'Automatic coffee maker'),
                (9, 'Running Shoes', 2, 119.99, 35, 'Comfortable running shoes'),
                (10, 'Tablet', 1, 399.99, 22, '10-inch tablet'),
            ]
            cursor.executemany("INSERT INTO products (id, name, category_id, price, stock_quantity, description) VALUES (?, ?, ?, ?, ?, ?)", products_data)

            customers_data = [
                (1, 'John Doe', 'john@example.com', '555-0101'),
                (2, 'Jane Smith', 'jane@example.com', '555-0102'),
                (3, 'Bob Johnson', 'bob@example.com', '555-0103'),
                (4, 'Alice Williams', 'alice@example.com', '555-0104'),
                (5, 'Charlie Brown', 'charlie@example.com', '555-0105'),
            ]
            cursor.executemany("INSERT INTO customers (id, name, email, phone) VALUES (?, ?, ?, ?)", customers_data)

            orders_data = [
                (1, 1, 1699.98, 'completed'),
                (2, 2, 109.98, 'completed'),
                (3, 3, 49.99, 'pending'),
                (4, 1, 199.99, 'completed'),
                (5, 4, 519.98, 'shipped'),
            ]
            cursor.executemany("INSERT INTO orders (id, customer_id, total_amount, status) VALUES (?, ?, ?, ?)", orders_data)

            order_items_data = [
                (1, 1, 1, 1, 999.99),  # John bought 1 laptop
                (2, 1, 2, 1, 699.99),  # John bought 1 smartphone
                (3, 2, 3, 2, 29.99),   # Jane bought 2 t-shirts
                (4, 2, 4, 1, 79.99),   # Jane bought 1 jeans
                (5, 3, 5, 1, 49.99),   # Bob bought 1 book
                (6, 4, 7, 1, 199.99),  # John bought headphones
                (7, 5, 10, 1, 399.99), # Alice bought tablet
                (8, 5, 9, 1, 119.99),  # Alice bought shoes
            ]
            cursor.executemany("INSERT INTO order_items VALUES (?, ?, ?, ?, ?)", order_items_data)

            conn.commit()
            logger.info("Sample database created successfully")

        except Exception as e:
            logger.error(f"Error creating sample database: {e}")
            conn.rollback()
        finally:
            conn.close()

    def execute_query(self, sql: str) -> QueryResult:
        """Execute SQL query and return results"""
        try:
            conn = sqlite3.connect(self.database_path)
            conn.row_factory = sqlite3.Row  # This enables column access by name
            cursor = conn.cursor()

            cursor.execute(sql)
            rows = cursor.fetchall()

            # Convert to list of dictionaries
            data = [dict(row) for row in rows]
            columns = [description[0] for description in cursor.description] if cursor.description else []

            conn.close()

            return QueryResult(
                success=True,
                data=data,
                columns=columns,
                row_count=len(data)
            )

        except Exception as e:
            logger.error(f"Error executing query: {e}")
            return QueryResult(
                success=False,
                error=str(e)
            )

    def get_schema(self) -> List[SchemaInfo]:
        """Get database schema information"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()

            # Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()

            schema_info = []
            for (table_name,) in tables:
                # Get column information
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns_info = cursor.fetchall()

                # Get foreign key information
                cursor.execute(f"PRAGMA foreign_key_list({table_name})")
                fk_info = cursor.fetchall()

                # Create a mapping of column names to foreign key info
                fk_map = {}
                for fk in fk_info:
                    # fk format: [id, seq, table, from_col, to_col, on_update, on_delete, match]
                    fk_map[fk[3]] = {'table': fk[2], 'column': fk[4]}

                columns = []
                for col_info in columns_info:
                    col_name = col_info[1]
                    column_data = {
                        'name': col_name,
                        'type': col_info[2],
                        'nullable': not col_info[3],
                        'primary_key': bool(col_info[5])
                    }

                    # Add foreign key information if available
                    if col_name in fk_map:
                        column_data['foreign_key'] = f"{fk_map[col_name]['table']}.{fk_map[col_name]['column']}"

                    columns.append(column_data)

                # Get row count
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cursor.fetchone()[0]

                schema_info.append(SchemaInfo(
                    name=table_name,
                    columns=columns,
                    row_count=row_count
                ))

            conn.close()
            return schema_info

        except Exception as e:
            logger.error(f"Error getting schema: {e}")
            return []

    def validate_sql(self, sql: str) -> Tuple[bool, str]:
        """Validate SQL for safety and syntax"""
        import re

        sql_stripped = sql.strip()
        sql_upper = sql_stripped.upper()

        # Check for dangerous operations using word boundaries
        dangerous_keywords = [
            'DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 'CREATE',
            'TRUNCATE', 'REPLACE', 'PRAGMA', 'ATTACH', 'DETACH'
        ]

        # Check for potentially dangerous patterns
        dangerous_patterns = [
            'UNION',  # Prevent UNION attacks
            ';',      # Prevent multiple statements
        ]

        # Use word boundaries to match whole words only
        for keyword in dangerous_keywords:
            if re.search(r'\b' + keyword + r'\b', sql_upper):
                return False, f"Forbidden SQL operation: {keyword}"

        for pattern in dangerous_patterns:
            if pattern in sql_upper:
                return False, f"Forbidden SQL pattern: {pattern}"

        # Must be a SELECT statement
        if not sql_upper.startswith('SELECT'):
            return False, "Only SELECT queries are allowed"

        # Enhanced syntax validation
        validation_result = self._validate_sql_syntax(sql_stripped)
        if not validation_result[0]:
            return validation_result

        # Table and column validation
        table_validation = self._validate_table_references(sql_stripped)
        if not table_validation[0]:
            return table_validation

        return True, "Valid SQL"

    def _validate_sql_syntax(self, sql: str) -> Tuple[bool, str]:
        """Enhanced SQL syntax validation"""
        # Basic parentheses matching
        if sql.count('(') != sql.count(')'):
            return False, "Mismatched parentheses"

        # Check for incomplete queries
        if sql.strip().endswith(','):
            return False, "Query appears incomplete (ends with comma)"

        # Check for common syntax errors
        sql_upper = sql.upper()

        # Check for orphaned table aliases
        import re

        # Look for table references like "p.column" without proper JOIN
        alias_refs = re.findall(r'\b(\w+)\.(\w+)', sql)
        if alias_refs:
            # Check if aliases are defined in FROM or JOIN clauses
            from_match = re.search(r'FROM\s+(\w+)(?:\s+AS\s+(\w+)|\s+(\w+))?', sql_upper)
            join_matches = re.findall(r'JOIN\s+(\w+)(?:\s+AS\s+(\w+)|\s+(\w+))?', sql_upper)

            defined_aliases = set()
            if from_match:
                table_name, as_alias, direct_alias = from_match.groups()
                if as_alias:
                    defined_aliases.add(as_alias.lower())
                elif direct_alias:
                    defined_aliases.add(direct_alias.lower())
                else:
                    defined_aliases.add(table_name.lower())

            for join_match in join_matches:
                table_name, as_alias, direct_alias = join_match
                if as_alias:
                    defined_aliases.add(as_alias.lower())
                elif direct_alias:
                    defined_aliases.add(direct_alias.lower())
                else:
                    defined_aliases.add(table_name.lower())

            # Check if used aliases are defined
            for alias, column in alias_refs:
                if alias.lower() not in defined_aliases:
                    return False, f"Undefined table alias '{alias}' used in '{alias}.{column}'"

        # Check for malformed WHERE clauses
        if 'WHERE' in sql_upper:
            where_part = sql_upper.split('WHERE')[1].split('GROUP BY')[0].split('ORDER BY')[0].split('LIMIT')[0]
            if 'IN (' in where_part and ')' not in where_part:
                return False, "Malformed WHERE clause with incomplete IN condition"

        return True, "Syntax validation passed"

    def _validate_table_references(self, sql: str) -> Tuple[bool, str]:
        """Validate that referenced tables exist in the database"""
        try:
            # Get available tables
            schema_info = self.get_schema()
            available_tables = {table.name.lower() for table in schema_info}

            # Extract table references from SQL
            import re
            sql_upper = sql.upper()

            # Find FROM clauses
            from_matches = re.findall(r'FROM\s+(\w+)', sql_upper)
            # Find JOIN clauses
            join_matches = re.findall(r'JOIN\s+(\w+)', sql_upper)

            referenced_tables = set()
            referenced_tables.update(table.lower() for table in from_matches)
            referenced_tables.update(table.lower() for table in join_matches)

            # Check if all referenced tables exist
            missing_tables = referenced_tables - available_tables
            if missing_tables:
                return False, f"Referenced table(s) do not exist: {', '.join(missing_tables)}"

            return True, "Table references validated"

        except Exception as e:
            # If validation fails, allow the query to proceed (non-critical validation)
            logger.warning(f"Table reference validation failed: {e}")
            return True, "Table validation skipped due to error"

    def get_table_relationships(self) -> List[Dict[str, Any]]:
        """Get table relationships based on foreign keys"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()

            # Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()

            relationships = []
            for (table_name,) in tables:
                # Get foreign key information for this table
                cursor.execute(f"PRAGMA foreign_key_list({table_name})")
                fk_info = cursor.fetchall()

                for fk in fk_info:
                    # fk format: [id, seq, table, from_col, to_col, on_update, on_delete, match]
                    relationship = {
                        'from_table': table_name,
                        'from_column': fk[3],
                        'to_table': fk[2],
                        'to_column': fk[4],
                        'relationship_type': 'foreign_key'
                    }
                    relationships.append(relationship)

            conn.close()
            return relationships

        except Exception as e:
            logger.error(f"Error getting table relationships: {e}")
            return []

    def is_connected(self) -> bool:
        """Check if database is connected"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.close()
            return True
        except Exception:
            return False

    @property
    def name(self) -> str:
        """Provider name"""
        return f"SQLite ({self.database_path})"