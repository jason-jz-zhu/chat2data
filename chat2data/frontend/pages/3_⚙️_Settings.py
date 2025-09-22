"""
Settings Page - Configuration management for Chat2Data
"""

import streamlit as st
import json
import asyncio
from pathlib import Path
import sys
import os

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from chat2data import Chat2Data
from chat2data.config.settings import Config
from chat2data.providers.llm.mock_provider import MockLLMProvider
from chat2data.providers.llm.ollama_provider import OllamaLLMProvider
from chat2data.providers.database.sqlite_provider import SQLiteDatabaseProvider
from chat2data.providers.vector.memory_provider import MemoryVectorStoreProvider

def test_connection(provider_type, database_path):
    """Test connection with given settings"""
    try:
        # Test LLM provider
        if provider_type == 'mock':
            llm_provider = MockLLMProvider()
        else:
            llm_provider = OllamaLLMProvider()

        # Test database provider
        database_provider = SQLiteDatabaseProvider(database_path)

        # Test vector store
        vector_store_provider = MemoryVectorStoreProvider()

        # Create Chat2Data instance
        chat2data = Chat2Data(
            llm_provider=llm_provider,
            database_provider=database_provider,
            vector_store_provider=vector_store_provider
        )

        # Run health check
        health = asyncio.run(chat2data.health_check())

        return True, health
    except Exception as e:
        return False, str(e)

def main():
    st.title("⚙️ Configuration Settings")
    st.markdown("Configure Chat2Data providers and connections")

    # Initialize session state for settings
    if 'provider_type' not in st.session_state:
        st.session_state.provider_type = 'mock'
    if 'database_path' not in st.session_state:
        st.session_state.database_path = './data/chat2data.db'
    if 'ollama_url' not in st.session_state:
        st.session_state.ollama_url = 'http://localhost:11434'
    if 'ollama_model' not in st.session_state:
        st.session_state.ollama_model = 'llama3.2:latest'

    # Provider Configuration
    st.header("🤖 LLM Provider Configuration")

    col1, col2 = st.columns(2)

    with col1:
        provider_type = st.selectbox(
            "LLM Provider",
            options=['mock', 'ollama'],
            index=0 if st.session_state.provider_type == 'mock' else 1,
            key="settings_provider_type",
            help="Select the LLM provider for SQL generation"
        )

        if provider_type == 'ollama':
            ollama_url = st.text_input(
                "Ollama URL",
                value=st.session_state.ollama_url,
                key="settings_ollama_url",
                help="URL of your Ollama server"
            )

            ollama_model = st.text_input(
                "Model Name",
                value=st.session_state.ollama_model,
                key="settings_ollama_model",
                help="Name of the Ollama model to use"
            )

            st.info("""
            **Ollama Setup Instructions:**
            1. Install Ollama: `curl -fsSL https://ollama.ai/install.sh | sh`
            2. Start Ollama: `ollama serve`
            3. Pull a model: `ollama pull llama3.2:latest`
            """)

    with col2:
        st.markdown("### Provider Information")

        if provider_type == 'mock':
            st.success("✅ Mock Provider (No dependencies)")
            st.markdown("""
            **Features:**
            - Zero external dependencies
            - Pattern-based SQL generation
            - Instant responses
            - Perfect for demos and testing
            """)
        else:
            st.warning("⚠️ Ollama Provider (Requires Ollama server)")
            st.markdown("""
            **Features:**
            - Local LLM inference
            - Better SQL generation
            - Supports multiple models
            - Privacy-focused (runs locally)
            """)

    st.divider()

    # Database Configuration
    st.header("🗄️ Database Configuration")

    col1, col2 = st.columns(2)

    with col1:
        database_path = st.text_input(
            "SQLite Database Path",
            value=st.session_state.database_path,
            key="settings_database_path",
            help="Path to your SQLite database file"
        )

        if st.button("📁 Browse Sample Databases", key="browse_sample_dbs"):
            st.info("""
            **Available Sample Databases:**
            - `./data/chat2data.db` - Main database with sample data
            - `:memory:` - In-memory database (temporary)
            """)

    with col2:
        st.markdown("### Database Information")

        if os.path.exists(database_path):
            file_size = os.path.getsize(database_path) / 1024 / 1024  # MB
            st.metric("File Size", f"{file_size:.2f} MB")
            st.success(f"✅ Database file exists")
        else:
            if database_path == ":memory:":
                st.info("📝 Using in-memory database")
            else:
                st.warning(f"⚠️ Database file not found: {database_path}")
                if st.button("Create Sample Database", key="create_sample_db"):
                    os.makedirs(os.path.dirname(database_path) or ".", exist_ok=True)
                    st.success(f"Database will be created at: {database_path}")

    st.divider()

    # Vector Store Configuration
    st.header("🔍 Vector Store Configuration")

    col1, col2 = st.columns(2)

    with col1:
        vector_provider = st.selectbox(
            "Vector Store Provider",
            options=['memory'],
            key="settings_vector_provider",
            help="Select the vector store provider for schema embeddings"
        )

        st.info("""
        **Coming Soon:**
        - ChromaDB integration
        - Pinecone support
        - Weaviate connector
        """)

    with col2:
        st.markdown("### Vector Store Information")
        st.success("✅ Memory Provider (Built-in)")
        st.markdown("""
        **Features:**
        - In-memory storage
        - Fast similarity search
        - No external dependencies
        - Automatic schema indexing
        """)

    st.divider()

    # Connection Testing
    st.header("🔌 Connection Testing")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🧪 Test All Connections", key="test_connections", type="primary"):
            with st.spinner("Testing connections..."):
                # Save settings to session state
                st.session_state.provider_type = provider_type
                st.session_state.database_path = database_path
                if provider_type == 'ollama':
                    st.session_state.ollama_url = ollama_url
                    st.session_state.ollama_model = ollama_model

                # Test connection
                success, result = test_connection(provider_type, database_path)

                if success:
                    st.success("✅ All connections successful!")

                    # Display health check results
                    st.markdown("### Health Check Results")
                    for component, status in result.items():
                        col_icon = "✅" if status.get('available', status.get('connected', False)) else "❌"
                        st.markdown(f"**{component}**: {col_icon} {status.get('name', 'Unknown')}")

                    # Clear existing Chat2Data instance to use new settings
                    st.session_state.chat2data = None
                else:
                    st.error(f"❌ Connection failed: {result}")

    with col2:
        if st.button("💾 Save Configuration", key="save_config"):
            config = {
                "llm": {
                    "provider": provider_type,
                    "model_name": ollama_model if provider_type == 'ollama' else None,
                    "base_url": ollama_url if provider_type == 'ollama' else None
                },
                "database": {
                    "provider": "sqlite",
                    "path": database_path
                },
                "vector_store": {
                    "provider": "memory"
                }
            }

            config_path = "chat2data_ui.json"
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)

            st.success(f"✅ Configuration saved to {config_path}")

    with col3:
        if st.button("🔄 Reset to Defaults", key="reset_defaults"):
            st.session_state.provider_type = 'mock'
            st.session_state.database_path = './data/chat2data.db'
            st.session_state.ollama_url = 'http://localhost:11434'
            st.session_state.ollama_model = 'llama3.2:latest'
            st.session_state.chat2data = None
            st.rerun()

    st.divider()

    # Advanced Settings
    with st.expander("🔧 Advanced Settings"):
        st.markdown("### Query Settings")

        col1, col2 = st.columns(2)

        with col1:
            query_timeout = st.number_input(
                "Query Timeout (seconds)",
                min_value=1,
                max_value=60,
                value=30,
                key="settings_query_timeout",
                help="Maximum time for query execution"
            )

            max_rows = st.number_input(
                "Maximum Result Rows",
                min_value=10,
                max_value=10000,
                value=1000,
                step=100,
                key="settings_max_rows",
                help="Maximum rows to return in query results"
            )

        with col2:
            enable_cache = st.checkbox(
                "Enable Query Cache",
                value=True,
                key="settings_enable_cache",
                help="Cache query results for faster repeated queries"
            )

            enable_suggestions = st.checkbox(
                "Enable Query Suggestions",
                value=True,
                key="settings_enable_suggestions",
                help="Show query suggestions based on schema"
            )

        st.markdown("### Security Settings")

        enable_sql_validation = st.checkbox(
            "Enable SQL Validation",
            value=True,
            key="settings_sql_validation",
            help="Validate SQL queries for dangerous operations",
            disabled=True
        )

        st.info("SQL validation is always enabled for security")

        allowed_operations = st.multiselect(
            "Allowed SQL Operations",
            options=["SELECT"],
            default=["SELECT"],
            key="settings_allowed_operations",
            disabled=True,
            help="Only SELECT operations are allowed for safety"
        )

    # Configuration Import/Export
    with st.expander("📤 Import/Export Configuration"):
        st.markdown("### Export Configuration")

        current_config = {
            "llm": {
                "provider": st.session_state.provider_type,
                "model_name": st.session_state.get('ollama_model'),
                "base_url": st.session_state.get('ollama_url')
            },
            "database": {
                "provider": "sqlite",
                "path": st.session_state.database_path
            },
            "vector_store": {
                "provider": "memory"
            }
        }

        config_json = json.dumps(current_config, indent=2)
        st.download_button(
            "📥 Download Configuration",
            data=config_json,
            file_name="chat2data_config.json",
            mime="application/json",
            key="download_config"
        )

        st.markdown("### Import Configuration")

        uploaded_file = st.file_uploader(
            "Choose a configuration file",
            type=['json'],
            key="upload_config_file",
            help="Upload a Chat2Data configuration JSON file"
        )

        if uploaded_file is not None:
            try:
                config_data = json.load(uploaded_file)

                # Update session state with imported config
                st.session_state.provider_type = config_data['llm']['provider']
                st.session_state.database_path = config_data['database']['path']

                if config_data['llm']['provider'] == 'ollama':
                    st.session_state.ollama_url = config_data['llm'].get('base_url', 'http://localhost:11434')
                    st.session_state.ollama_model = config_data['llm'].get('model_name', 'llama3.2:latest')

                st.success("✅ Configuration imported successfully!")
                st.session_state.chat2data = None
                st.rerun()

            except Exception as e:
                st.error(f"Error importing configuration: {str(e)}")

if __name__ == "__main__":
    main()