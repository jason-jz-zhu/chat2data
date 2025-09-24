# Chat2Data

A Python framework for converting natural language queries into SQL using Large Language Models (LLMs).

## 🚀 Quick Start

### Installation

#### Option 1: Using uv (Recommended - Fast)
```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh
# or on macOS
brew install uv

# Clone the repository
git clone <your-repo-url>
cd chat2data

# Create virtual environment and install
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

#### Option 2: Using pip
```bash
# Clone the repository
git clone <your-repo-url>
cd chat2data

# Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the package
pip install -e .
```

### Quick Test
```bash
# Run the comprehensive example to verify everything works
python example.py
```

## 🌟 NEW: Interactive Web UI

**Note**: For Web UI functionality, install frontend dependencies first:
```bash
# Option 1: Install with frontend dependencies (note the quotes for shell compatibility)
pip install 'chat2data[frontend]'

# Option 2: Install Streamlit separately
pip install streamlit
```

Launch the Chat2Data web interface with a single command:

```bash
# Launch the Streamlit UI
python -m chat2data.cli.main ui

# Or with custom options
python -m chat2data.cli.main ui --host 0.0.0.0 --port 8080 --no-browser
```

The UI provides:
- 💬 **Chat Interface** - Natural language query input with chat history
- 📊 **Schema Explorer** - Browse database tables and columns
- 📈 **Data Visualization** - Automatic charts and graphs
- ⚙️ **Settings** - Configure providers and connections
- 💾 **Export Options** - Download results as CSV, JSON, or SQL

## 📖 Step-by-Step Usage Guide

### Step 1: Launch the Web UI (Easiest Way)

```bash
# Install the package
pip install -e .

# Install UI dependencies (use quotes for shell compatibility)
pip install 'chat2data[frontend]'

# Launch the UI
python -m chat2data.cli.main ui
```

Your browser will open automatically at http://localhost:8501

### Step 2: Basic Programmatic Usage

Create a file `my_app.py`:

```python
import asyncio
from chat2data import Chat2Data
from chat2data.providers.llm.ollama_provider import OllamaLLMProvider
from chat2data.providers.llm.mock_provider import MockLLMProvider
from chat2data.providers.database.sqlite_provider import SQLiteDatabaseProvider
from chat2data.providers.vector.memory_provider import MemoryVectorStoreProvider

async def main():
    # Try to use Ollama first, fallback to mock if unavailable
    try:
        llm_provider = OllamaLLMProvider()
        if not llm_provider.is_available():
            print("⚠️  Ollama not available, using mock provider")
            llm_provider = MockLLMProvider()
    except Exception:
        llm_provider = MockLLMProvider()

    # Initialize Chat2Data
    chat2data = Chat2Data(
        llm_provider=llm_provider,
        database_provider=SQLiteDatabaseProvider("data/chat2data.db"),
        vector_store_provider=MemoryVectorStoreProvider()
    )

    # Example queries
    queries = [
        "Show me all products",
        "Count all customers",
        "What are the top 5 expensive items?",
        "Show total sales amount"
    ]

    for query in queries:
        print(f"\n📝 Query: {query}")
        result = await chat2data.query(query)

        if result['success']:
            print(f"✅ SQL: {result['sql']}")
            print(f"📊 Rows returned: {len(result.get('data', []))}")
        else:
            print(f"❌ Error: {result['error']}")

asyncio.run(main())
```

### Step 3: CLI Usage

```bash
# Check system status
python -m chat2data.cli.main status

# Show configuration
python -m chat2data.cli.main config-show

# Run a demo query
python -m chat2data.cli.main demo --query "Show all products"

# Interactive mode
python -m chat2data.cli.main demo --interactive

# Launch the web UI
python -m chat2data.cli.main ui
```

### Step 4: Real-World Examples

#### E-Commerce Analytics
```python
async def ecommerce_analytics():
    # Use real LLM for better results
    llm_provider = OllamaLLMProvider() if OllamaLLMProvider().is_available() else MockLLMProvider()

    chat2data = Chat2Data(
        llm_provider=llm_provider,
        database_provider=SQLiteDatabaseProvider("data/chat2data.db"),
        vector_store_provider=MemoryVectorStoreProvider()
    )

    # Business queries
    queries = [
        "How many products do we have in each category?",
        "What is the average price of products?",
        "Show me the most expensive products",
        "List customers who made purchases",
        "What is the total revenue?"
    ]

    for q in queries:
        result = await chat2data.query(q)
        print(f"Q: {q}")
        print(f"A: {result['sql']}\n")

asyncio.run(ecommerce_analytics())
```

#### Database Schema Exploration
```python
async def explore_database():
    # Use real LLM for better results
    llm_provider = OllamaLLMProvider() if OllamaLLMProvider().is_available() else MockLLMProvider()

    chat2data = Chat2Data(
        llm_provider=llm_provider,
        database_provider=SQLiteDatabaseProvider("data/chat2data.db"),
        vector_store_provider=MemoryVectorStoreProvider()
    )

    # Get schema information
    schema = chat2data.database.get_schema()

    print("📊 Database Schema:")
    for table in schema:
        print(f"\nTable: {table.name}")
        print(f"Columns: {', '.join([c['name'] for c in table.columns])}")
        print(f"Row count: {table.row_count}")

asyncio.run(explore_database())
```

#### Error Handling
```python
async def handle_errors():
    # Use real LLM for better results
    llm_provider = OllamaLLMProvider() if OllamaLLMProvider().is_available() else MockLLMProvider()

    chat2data = Chat2Data(
        llm_provider=llm_provider,
        database_provider=SQLiteDatabaseProvider("data/chat2data.db"),
        vector_store_provider=MemoryVectorStoreProvider()
    )

    # Test error scenarios
    test_queries = [
        "Delete all data",  # Should be blocked
        "Drop table products",  # Should be blocked
        "Show me the data from non_existent_table",  # Table doesn't exist
    ]

    for query in test_queries:
        result = await chat2data.query(query)
        if not result['success']:
            print(f"Query: {query}")
            print(f"Blocked/Error: {result.get('error', 'Unknown error')}\n")

asyncio.run(handle_errors())
```

## 🔧 Configuration

### LLM Providers

Chat2Data now uses **real LLM providers by default** for actual SQL generation capabilities.

#### Ollama Provider (RECOMMENDED - Default)

**Prerequisites**: Install and run Ollama locally:
```bash
# Install Ollama (visit https://ollama.ai for installation instructions)
# Then pull recommended models:
ollama pull llama3.2:latest
ollama pull sqlcoder:latest  # Optional: specialized SQL model
```

```python
from chat2data.providers.llm.ollama_provider import OllamaLLMProvider

# Basic Ollama provider (uses central config defaults)
llm_provider = OllamaLLMProvider()

# Or with custom settings
llm_provider = OllamaLLMProvider(
    base_url='http://localhost:11434',
    model_name='llama3.2:latest'
)
```

#### Enhanced Ollama Provider (Advanced)
For better context handling and improved SQL generation:
```python
from chat2data.providers.llm.enhanced_ollama_provider import EnhancedOllamaLLMProvider

llm_provider = EnhancedOllamaLLMProvider(
    model_name='llama3.2:latest',
    base_url='http://localhost:11434'
)
```

#### Mock Provider (Testing/Fallback)
```python
from chat2data.providers.llm.mock_provider import MockLLMProvider
# Only for testing or when real LLM is not available
llm_provider = MockLLMProvider()
```

#### Custom OpenAI Provider
```python
from chat2data.core.base import LLMProvider
import openai

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key):
        self.api_key = api_key
        openai.api_key = api_key

    async def generate_sql(self, question: str, schema: str) -> str:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"Convert to SQL. Schema: {schema}"},
                {"role": "user", "content": question}
            ]
        )
        return response.choices[0].message.content

    async def health_check(self) -> dict:
        return {'name': 'OpenAI', 'available': True}

# Use it
chat2data = Chat2Data(
    llm_provider=OpenAIProvider("your-api-key"),
    database_provider=SQLiteDatabaseProvider("data/chat2data.db"),
    vector_store_provider=MemoryVectorStoreProvider()
)
```

## 📁 Project Structure

```
chat2data/
├── README.md              # This file
├── example.py            # Comprehensive example
├── pyproject.toml        # Package configuration
├── chat2data/            # Main package
│   ├── core/            # Core framework
│   │   ├── base.py      # Base provider classes
│   │   └── chat2data.py # Main orchestration
│   ├── providers/       # Modular providers
│   │   ├── llm/        # Language model providers
│   │   ├── database/   # Database providers
│   │   └── vector/     # Vector store providers
│   ├── cli/            # CLI interface
│   └── config/         # Configuration
└── data/
    └── chat2data.db     # Sample database
```

## 🎯 Common Use Cases

### 1. Business Intelligence Dashboard
- Query sales data in natural language
- Generate reports without SQL knowledge
- Real-time analytics

### 2. Data Exploration Tool
- Explore new databases quickly
- Understand schema and relationships
- Test queries safely

### 3. API Backend
- Build natural language query APIs
- Integrate into existing applications
- Provide data access to non-technical users

## 📊 Sample Queries

The framework understands various query patterns:

```python
# Basic queries
"Show all products"
"List all customers"
"Display all orders"

# Counting
"Count all products"
"How many customers do we have?"
"Number of orders"

# Filtering
"Show expensive products"
"Products over $500"
"Recent orders"

# Top N queries
"Top 5 expensive products"
"Show 10 latest orders"
"Best selling products"

# Aggregations
"Total sales amount"
"Average product price"
"Sum of all orders"

# Grouping
"Sales by category"
"Orders by customer"
"Products by price range"
```

## ✅ Key Features

- **Zero External Dependencies** - Mock provider works out of the box
- **Secure** - SQL injection prevention built-in
- **Extensible** - Easy to add custom providers
- **Production Ready** - Comprehensive error handling
- **Well Documented** - Clear examples for every use case
- **Modular Architecture** - Swap providers easily
- **Schema-Aware** - Automatic database understanding

## 🛠️ Troubleshooting

### Common Issues

1. **ModuleNotFoundError**
   ```bash
   pip install -e .
   ```

2. **Database not found**
   - Check path: `data/chat2data.db`
   - Run example to create: `python example.py`

3. **LLM provider errors**
   - Use mock provider for testing
   - Check Ollama is running if using Ollama provider

4. **Empty results**
   - Verify database has data
   - Try simpler queries first

## 📝 API Reference

### Chat2Data Class

```python
# Initialize with real LLM provider
from chat2data.providers.llm.ollama_provider import OllamaLLMProvider

llm_provider = OllamaLLMProvider() if OllamaLLMProvider().is_available() else MockLLMProvider()

chat2data = Chat2Data(
    llm_provider=llm_provider,
    database_provider=SQLiteDatabaseProvider("data/chat2data.db"),
    vector_store_provider=MemoryVectorStoreProvider()
)

# Query
result = await chat2data.query("Your question here")

# Response format
{
    'success': bool,
    'sql': str,           # Generated SQL
    'data': list,         # Query results
    'error': str          # Error message if failed
}

# Get schema
schema = chat2data.database.get_schema()

# Health check
health = await chat2data.health_check()
```

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Add new providers (OpenAI, Anthropic, etc.)
- Support more databases (PostgreSQL, MySQL, etc.)
- Improve query understanding
- Add more examples

## 📄 License

MIT License