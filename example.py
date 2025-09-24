#!/usr/bin/env python3
"""
Chat2Data - Comprehensive Usage Example

This example demonstrates all major features of Chat2Data:
- Basic setup and initialization
- Health checks and schema inspection
- Natural language queries
- CLI usage patterns
- Custom provider configuration
- Error handling

Prerequisites:
- Install: pip install -e .
- Data: Sample database included at data/chat2data.db
"""

import asyncio
import sys
from pathlib import Path

# Add the current directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

from chat2data import Chat2Data
from chat2data.providers.llm.ollama_provider import OllamaLLMProvider
from chat2data.providers.llm.mock_provider import MockLLMProvider
from chat2data.providers.database.sqlite_provider import SQLiteDatabaseProvider
from chat2data.providers.vector.memory_provider import MemoryVectorStoreProvider


async def basic_usage_example():
    """Basic Chat2Data usage with Ollama provider (fallback to mock if unavailable)"""
    print("=" * 60)
    print("🚀 BASIC USAGE EXAMPLE")
    print("=" * 60)

    # Try to use Ollama first, fallback to mock if not available
    try:
        llm_provider = OllamaLLMProvider()
        if llm_provider.is_available():
            print("✅ Using Ollama LLM provider")
        else:
            print("⚠️  Ollama not available, using mock provider")
            llm_provider = MockLLMProvider()
    except Exception as e:
        print(f"⚠️  Failed to initialize Ollama ({e}), using mock provider")
        llm_provider = MockLLMProvider()

    # Initialize Chat2Data with selected provider
    chat2data = Chat2Data(
        llm_provider=llm_provider,
        database_provider=SQLiteDatabaseProvider("data/chat2data.db"),
        vector_store_provider=MemoryVectorStoreProvider()
    )

    print("✅ Chat2Data initialized successfully")

    # Health check
    health = await chat2data.health_check()
    print("\n🏥 System Health:")
    for component, status in health.items():
        available = status.get('available', status.get('connected', False))
        icon = "✅" if available else "❌"
        print(f"   {component}: {icon} {status['name']}")

    # Show database schema
    schema = chat2data.get_schema()
    print(f"\n📊 Database Schema ({len(schema)} tables):")
    for table in schema:
        print(f"   • {table.name}: {table.row_count} rows")
        if table.columns:
            cols = ", ".join([f"{col['name']}({col['type']})" for col in table.columns[:3]])
            if len(table.columns) > 3:
                cols += f", ... +{len(table.columns)-3} more"
            print(f"     Columns: {cols}")

    # Example queries
    queries = [
        "Show me all the data in the first table",
        "How many records are in total?",
        "What are the column names of all tables?",
        "Give me a summary of the data"
    ]

    print(f"\n🔍 Running {len(queries)} example queries:")
    print("-" * 40)

    for i, query in enumerate(queries, 1):
        print(f"\n{i}. Query: '{query}'")

        try:
            result = await chat2data.query(query)

            if result['success']:
                print(f"   Generated SQL: {result['sql']}")

                if result['result']['success']:
                    data = result['result']['data']
                    print(f"   Results: {len(data)} rows")

                    # Show sample data
                    if data and len(data) > 0:
                        print(f"   Sample: {data[0]}")
                        if len(data) > 1:
                            print(f"   ... and {len(data)-1} more rows")
                else:
                    print(f"   Database Error: {result['result'].get('error', 'Unknown error')}")
            else:
                print(f"   Query Error: {result.get('error', 'Unknown error')}")

        except Exception as e:
            print(f"   Exception: {str(e)}")


async def error_handling_example():
    """Demonstrate error handling"""
    print("\n" + "=" * 60)
    print("⚠️  ERROR HANDLING EXAMPLE")
    print("=" * 60)

    # Use the same provider selection logic as basic example
    try:
        llm_provider = OllamaLLMProvider()
        if not llm_provider.is_available():
            llm_provider = MockLLMProvider()
    except Exception:
        llm_provider = MockLLMProvider()

    chat2data = Chat2Data(
        llm_provider=llm_provider,
        database_provider=SQLiteDatabaseProvider("data/chat2data.db"),
        vector_store_provider=MemoryVectorStoreProvider()
    )

    # Test queries that might cause errors
    error_queries = [
        "SELECT * FROM nonexistent_table",  # Table doesn't exist
        "INVALID SQL SYNTAX HERE",          # Invalid SQL
        "",                                 # Empty query
        "DROP DATABASE everything",         # Potentially dangerous query
    ]

    print("Testing error scenarios:")

    for i, query in enumerate(error_queries, 1):
        print(f"\n{i}. Testing: '{query}'")

        try:
            result = await chat2data.query(query)

            if result['success']:
                if result['result']['success']:
                    print("   ✅ Query succeeded unexpectedly")
                else:
                    print(f"   ⚠️  Database error (expected): {result['result'].get('error')}")
            else:
                print(f"   ⚠️  Query error (expected): {result.get('error')}")

        except Exception as e:
            print(f"   ⚠️  Exception (expected): {str(e)}")


def cli_usage_examples():
    """Show CLI usage examples"""
    print("\n" + "=" * 60)
    print("💻 CLI USAGE EXAMPLES")
    print("=" * 60)

    print("After installation, you can use Chat2Data from the command line:")
    print()
    print("1. Interactive mode:")
    print("   chat2data --interactive")
    print()
    print("2. Direct query:")
    print("   chat2data --query 'Show me all products'")
    print()
    print("3. Specify database:")
    print("   chat2data --database ./data/chat2data.db --query 'Count all records'")
    print()
    print("4. Use different LLM provider:")
    print("   chat2data --llm-provider ollama --query 'Analyze the data'")
    print()
    print("5. Get help:")
    print("   chat2data --help")
    print()
    print("6. Health check:")
    print("   chat2data --health")


async def custom_configuration_example():
    """Show how to configure with different providers"""
    print("\n" + "=" * 60)
    print("⚙️  CUSTOM CONFIGURATION EXAMPLE")
    print("=" * 60)

    print("Example configurations for different providers:")
    print()

    # Ollama provider example (now the primary)
    print("1. Ollama Provider (local LLM - RECOMMENDED):")
    print("   from chat2data.providers.llm.ollama_provider import OllamaLLMProvider")
    print("   llm_provider = OllamaLLMProvider(")
    print("       base_url='http://localhost:11434',")
    print("       model_name='llama3.2:latest'")
    print("   )")
    print()

    # Mock provider example (for testing/fallback)
    print("2. Mock Provider (for testing/fallback):")
    print("   from chat2data.providers.llm.mock_provider import MockLLMProvider")
    print("   llm_provider = MockLLMProvider()")
    print()

    # Database providers
    print("3. Database Providers:")
    print("   # SQLite")
    print("   from chat2data.providers.database.sqlite_provider import SQLiteDatabaseProvider")
    print("   db_provider = SQLiteDatabaseProvider('path/to/database.db')")
    print()
    print("   # Can be extended for PostgreSQL, MySQL, etc.")
    print()

    # Vector store providers
    print("4. Vector Store Providers:")
    print("   # In-memory (for demos)")
    print("   from chat2data.providers.vector.memory_provider import MemoryVectorStoreProvider")
    print("   vector_provider = MemoryVectorStoreProvider()")
    print()
    print("   # Can be extended for Pinecone, Weaviate, etc.")


async def main():
    """Run all examples"""
    print("Chat2Data - Comprehensive Usage Examples")
    print("This script demonstrates all major features of Chat2Data")
    print()

    # Check if database exists
    db_path = Path("data/chat2data.db")
    if not db_path.exists():
        print("❌ Error: Sample database not found at data/chat2data.db")
        print("Please ensure you have the sample database file.")
        return

    try:
        # Run programmatic examples
        await basic_usage_example()
        await error_handling_example()

        # Show CLI and configuration examples
        cli_usage_examples()
        await custom_configuration_example()

        print("\n" + "=" * 60)
        print("✨ ALL EXAMPLES COMPLETED!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("• Try your own queries with: chat2data --interactive")
        print("• Connect to your own database")
        print("• Set up Ollama locally for real LLM functionality (ollama.ai)")
        print("• Try different models: ollama pull llama3.2, ollama pull sqlcoder")
        print("• Explore the source code in chat2data/ directory")
        print("• Read the documentation in README.md")

    except Exception as e:
        print(f"\n❌ Error running examples: {str(e)}")
        print("Make sure Chat2Data is properly installed: pip install -e .")


if __name__ == "__main__":
    asyncio.run(main())