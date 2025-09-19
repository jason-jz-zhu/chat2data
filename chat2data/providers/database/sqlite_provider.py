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

                columns = []
                for col_info in columns_info:
                    columns.append({
                        'name': col_info[1],
                        'type': col_info[2],
                        'nullable': not col_info[3],
                        'primary_key': bool(col_info[5])
                    })

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
        """Validate SQL for safety"""
        sql_upper = sql.upper().strip()

        # Check for dangerous operations
        dangerous_keywords = [
            'DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 'CREATE',
            'TRUNCATE', 'REPLACE', 'PRAGMA', 'ATTACH', 'DETACH'
        ]

        # Check for potentially dangerous patterns
        dangerous_patterns = [
            'UNION',  # Prevent UNION attacks
            ';',      # Prevent multiple statements
        ]

        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                return False, f"Forbidden SQL operation: {keyword}"

        for pattern in dangerous_patterns:
            if pattern in sql_upper:
                return False, f"Forbidden SQL pattern: {pattern}"

        # Must be a SELECT statement
        if not sql_upper.startswith('SELECT'):
            return False, "Only SELECT queries are allowed"

        # Basic syntax validation
        if sql.count('(') != sql.count(')'):
            return False, "Mismatched parentheses"

        return True, "Valid SQL"

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