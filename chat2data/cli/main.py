"""Main CLI interface for Chat2Data"""

import click
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from ..config.settings import Config
from ..config.central_config import get_config
from ..core.chat2data import Chat2Data
from ..providers.llm.mock_provider import MockLLMProvider
from ..providers.llm.ollama_provider import OllamaLLMProvider
from ..providers.database.sqlite_provider import SQLiteDatabaseProvider
from ..providers.vector.memory_provider import MemoryVectorStoreProvider

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


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
    if config.database.provider == "sqlite":
        database_provider = SQLiteDatabaseProvider(config.database.path)
    else:
        raise ValueError(f"Unsupported database provider: {config.database.provider}")

    # Initialize vector store provider
    if config.vector_store.provider == "memory":
        vector_store_provider = MemoryVectorStoreProvider()
    else:
        vector_store_provider = MemoryVectorStoreProvider()  # Fallback

    return Chat2Data(
        llm_provider=llm_provider,
        database_provider=database_provider,
        vector_store_provider=vector_store_provider
    )


@click.group()
@click.option('--config', '-c', help='Configuration file path')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.pass_context
def cli(ctx, config: Optional[str], verbose: bool):
    """Chat2Data - Natural Language to SQL Framework"""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load configuration
    if config:
        ctx.obj = Config.from_file(config)
    else:
        ctx.obj = Config.auto_detect()


@cli.command()
@click.option('--provider', default=None, type=click.Choice(['mock', 'ollama']),
              help='LLM provider to use')
@click.option('--database', default=None, help='Database path')
@click.option('--force', is_flag=True, help='Overwrite existing configuration')
@click.pass_context
def init(ctx, provider: Optional[str], database: Optional[str], force: bool):
    """Initialize Chat2Data configuration"""
    config_file = "chat2data.json"

    if os.path.exists(config_file) and not force:
        click.echo(f"Configuration file {config_file} already exists. Use --force to overwrite.")
        return

    # Get central configuration defaults
    central_config = get_config()

    # Create configuration
    config = Config()
    config.llm.provider = provider or central_config.llm.provider
    config.database.path = database or central_config.database.path

    # Create database directory
    Path(config.database.path).parent.mkdir(parents=True, exist_ok=True)

    # Save configuration
    if config.save_to_file(config_file):
        click.echo(f"✅ Configuration saved to {config_file}")
        click.echo(f"   LLM Provider: {provider}")
        click.echo(f"   Database: {database}")

        # Test the configuration
        try:
            chat2data = create_chat2data_instance(config)
            health = asyncio.run(chat2data.health_check())
            click.echo("\n🔍 Health Check:")
            for component, status in health.items():
                status_icon = "✅" if status.get('available', status.get('connected', False)) else "❌"
                click.echo(f"   {component}: {status_icon} {status['name']}")

        except Exception as e:
            click.echo(f"⚠️  Warning: {e}")
    else:
        click.echo("❌ Failed to save configuration")


@cli.command()
@click.option('--host', default=None, help='Server host')
@click.option('--port', default=None, type=int, help='Server port')
@click.option('--debug', is_flag=True, help='Debug mode')
@click.pass_context
def run(ctx, host: Optional[str], port: Optional[int], debug: bool):
    """Run Chat2Data server"""
    config = ctx.obj

    # Override config with CLI options
    if host:
        config.server.host = host
    if port:
        config.server.port = port
    if debug:
        config.server.debug = debug

    try:
        # Import Flask app components
        from ..backend.app import create_app
        app = create_app(config)

        click.echo(f"🚀 Starting Chat2Data server...")
        click.echo(f"   Host: {config.server.host}")
        click.echo(f"   Port: {config.server.port}")
        click.echo(f"   Debug: {config.server.debug}")
        click.echo(f"   LLM: {config.llm.provider}")
        click.echo(f"   Database: {config.database.path}")

        app.run(
            host=config.server.host,
            port=config.server.port,
            debug=config.server.debug
        )

    except ImportError as e:
        click.echo(f"❌ Error importing Flask app: {e}")
        click.echo("Make sure all dependencies are installed: pip install flask flask-cors")
    except Exception as e:
        click.echo(f"❌ Error starting server: {e}")


@cli.command()
@click.option('--query', '-q', help='Natural language query to execute')
@click.option('--interactive', '-i', is_flag=True, help='Interactive mode')
@click.pass_context
def demo(ctx, query: Optional[str], interactive: bool):
    """Run Chat2Data in demo mode with sample data"""
    config = ctx.obj

    # Force demo configuration using central config defaults
    central_config = get_config()
    config.llm.provider = "mock"
    config.database.path = central_config.database.demo_path

    try:
        chat2data = create_chat2data_instance(config)

        click.echo("🎭 Chat2Data Demo Mode")
        click.echo("Using mock LLM provider and sample SQLite database")

        # Show available tables
        schema = chat2data.get_schema()
        if schema:
            click.echo("\n📊 Available Tables:")
            for table in schema:
                click.echo(f"   • {table.name} ({table.row_count} rows)")

        if query:
            # Single query mode
            asyncio.run(execute_demo_query(chat2data, query))
        elif interactive:
            # Interactive mode
            asyncio.run(interactive_demo(chat2data))
        else:
            # Generate dynamic example queries based on schema
            try:
                schema = chat2data.get_schema()
                if schema and len(schema) > 0:
                    table_names = [table.name for table in schema]
                    primary_table = table_names[0]

                    example_queries = [
                        f"Show me all {primary_table}",
                        f"Count total {primary_table}",
                        f"What are the top 5 {primary_table}?",
                        f"Show first 10 {primary_table}",
                        "What tables are available?"
                    ]
                else:
                    # Fallback for when no schema is available
                    example_queries = [
                        "Show all available data",
                        "Count total records",
                        "What data is available?",
                        "Display table information",
                        "Show database structure"
                    ]
            except Exception:
                # Fallback for any errors
                example_queries = [
                    "Show all available data",
                    "Count total records",
                    "What data is available?",
                    "Display table information",
                    "Show database structure"
                ]

            click.echo("\n💡 Example Queries:")
            for i, example in enumerate(example_queries, 1):
                click.echo(f"   {i}. {example}")

            click.echo("\nRun with --interactive for interactive mode")
            click.echo("Or use --query 'your question here' for single queries")

    except Exception as e:
        click.echo(f"❌ Error in demo mode: {e}")


async def execute_demo_query(chat2data: Chat2Data, query: str):
    """Execute a single demo query"""
    click.echo(f"\n🤔 Query: {query}")

    result = await chat2data.query(query)

    if result['success']:
        click.echo(f"🔍 Generated SQL: {result['sql']}")

        if result['result']['success'] and result['result']['data']:
            data = result['result']['data']
            click.echo(f"📋 Results ({len(data)} rows):")

            # Show first few rows
            for i, row in enumerate(data[:5]):
                click.echo(f"   Row {i+1}: {row}")

            if len(data) > 5:
                click.echo(f"   ... and {len(data) - 5} more rows")

            if result.get('summary'):
                click.echo(f"📝 Summary: {result['summary']}")
        else:
            click.echo(f"❌ Query failed: {result['result'].get('error', 'Unknown error')}")
    else:
        click.echo(f"❌ Error: {result.get('error', 'Unknown error')}")


async def interactive_demo(chat2data: Chat2Data):
    """Run interactive demo mode"""
    click.echo("\n🎮 Interactive Demo Mode")
    click.echo("Type your questions or 'quit' to exit")

    while True:
        try:
            query = click.prompt("\n💬 Your question", type=str)

            if query.lower() in ['quit', 'exit', 'q']:
                click.echo("👋 Goodbye!")
                break

            await execute_demo_query(chat2data, query)

        except (KeyboardInterrupt, EOFError):
            click.echo("\n👋 Goodbye!")
            break
        except Exception as e:
            click.echo(f"❌ Error: {e}")


@cli.command()
@click.pass_context
def status(ctx):
    """Show Chat2Data status and configuration"""
    config = ctx.obj

    click.echo("📊 Chat2Data Status")
    click.echo(f"   LLM Provider: {config.llm.provider}")
    click.echo(f"   Database: {config.database.path}")
    click.echo(f"   Vector Store: {config.vector_store.provider}")

    try:
        chat2data = create_chat2data_instance(config)
        health = asyncio.run(chat2data.health_check())

        click.echo("\n🔍 Health Check:")
        for component, status in health.items():
            status_icon = "✅" if status.get('available', status.get('connected', False)) else "❌"
            click.echo(f"   {component}: {status_icon} {status['name']}")

    except Exception as e:
        click.echo(f"❌ Error checking status: {e}")


@cli.command()
@click.option('--format', default='json', type=click.Choice(['json', 'yaml']),
              help='Configuration format')
@click.pass_context
def config_show(ctx, format: str):
    """Show current configuration"""
    config = ctx.obj

    if format == 'json':
        import json
        click.echo(json.dumps(config.to_dict(), indent=2))
    elif format == 'yaml':
        try:
            import yaml
            click.echo(yaml.dump(config.to_dict(), default_flow_style=False))
        except ImportError:
            click.echo("PyYAML not installed. Install with: pip install pyyaml")
            click.echo("\nFalling back to JSON:")
            import json
            click.echo(json.dumps(config.to_dict(), indent=2))


@cli.command()
@click.option('--host', default='localhost', help='Streamlit server host')
@click.option('--port', default=8501, type=int, help='Streamlit server port')
@click.option('--browser/--no-browser', default=True, help='Open browser automatically')
@click.pass_context
def ui(ctx, host: str, port: int, browser: bool):
    """Launch Chat2Data Streamlit UI"""
    try:
        import streamlit.web.cli as stcli
        import sys
        from pathlib import Path

        # Find the streamlit app path
        app_path = Path(__file__).parent.parent / "frontend" / "streamlit_app.py"

        if not app_path.exists():
            click.echo(f"❌ Streamlit app not found at {app_path}")
            return

        click.echo("🚀 Launching Chat2Data UI...")
        click.echo(f"   Host: {host}")
        click.echo(f"   Port: {port}")
        click.echo(f"   Browser: {'Yes' if browser else 'No'}")

        # Prepare streamlit arguments
        args = [
            "streamlit",
            "run",
            str(app_path),
            f"--server.address={host}",
            f"--server.port={port}",
        ]

        if not browser:
            args.append("--server.headless=true")

        # Update sys.argv for streamlit
        sys.argv = args

        # Run streamlit
        stcli.main()

    except ImportError:
        click.echo("❌ Streamlit not installed. Install with: pip install streamlit")
        click.echo("Or install all frontend dependencies: pip install chat2data[frontend]")
    except Exception as e:
        click.echo(f"❌ Error launching UI: {e}")


if __name__ == '__main__':
    cli()