"""
Chat2Data - Onboarding & Setup Wizard
Guide users through initial configuration and setup
"""

import streamlit as st
import asyncio
import json
import time
from pathlib import Path
import sys
import os

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from chat2data import Chat2Data
from chat2data.core.enhanced_chat2data import EnhancedChat2Data
from chat2data.providers.llm.mock_provider import MockLLMProvider
from chat2data.providers.llm.enhanced_ollama_provider import EnhancedOllamaLLMProvider
from chat2data.providers.database.sqlite_provider import SQLiteDatabaseProvider
from chat2data.providers.vector.memory_provider import MemoryVectorStoreProvider
from chat2data.providers.vector.semantic_provider import SemanticVectorStoreProvider
from chat2data.frontend.utils.session_manager import (
    init_session_state,
    get_session_value,
    set_session_value,
    get_onboarding_status,
    set_onboarding_step,
    set_setup_mode,
    mark_onboarding_complete,
    reset_onboarding
)

# Page configuration
st.set_page_config(
    page_title="Chat2Data - Setup & Configuration",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize session state
init_session_state()

import logging
logger = logging.getLogger(__name__)

def test_ollama_connection():
    """Test Ollama connection and get available models"""
    try:
        ollama_url = get_session_value("ollama_url", "http://localhost:11434")
        import requests
        response = requests.get(f"{ollama_url}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            return True, [m.get('name', '') for m in models]
        return False, []
    except Exception as e:
        logger.error(f"Failed to test Ollama: {e}")
        return False, []

# Custom CSS for onboarding wizard
st.markdown("""<style>
.progress-container {
    background: #f0f2f6;
    border-radius: 10px;
    padding: 1rem;
    margin-bottom: 2rem;
}

.progress-step {
    display: inline-block;
    width: 20%;
    text-align: center;
    position: relative;
}

.step-circle {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    margin: 0 auto;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    color: white;
}

.step-active {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
}

.step-completed {
    background: #10b981;
}

.step-pending {
    background: #d1d5db;
}

.setup-card {
    background: white;
    border-radius: 15px;
    padding: 2rem;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    margin-bottom: 1.5rem;
    transition: all 0.3s ease;
}

.setup-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 8px 15px rgba(0,0,0,0.15);
}

.setup-mode-card {
    background: linear-gradient(135deg, #f6f8fb 0%, #e9ecef 100%);
    border: 2px solid transparent;
    border-radius: 15px;
    padding: 2rem;
    cursor: pointer;
    transition: all 0.3s ease;
}

.setup-mode-card:hover {
    border-color: #667eea;
    background: linear-gradient(135deg, #ffffff 0%, #f6f8fb 100%);
    transform: scale(1.02);
}

.status-indicator {
    padding: 0.5rem 1rem;
    border-radius: 20px;
    font-weight: 600;
    display: inline-block;
}

.status-success {
    background: #d1fae5;
    color: #065f46;
}

.status-error {
    background: #fee2e2;
    color: #991b1b;
}

.status-pending {
    background: #e0e7ff;
    color: #3730a3;
}

.main-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 2rem;
    border-radius: 15px;
    margin-bottom: 2rem;
    text-align: center;
}
</style>""", unsafe_allow_html=True)


def render_progress_bar(current_step):
    """Render the progress bar for onboarding steps"""
    steps = [
        ("1", "Welcome"),
        ("2", "LLM Setup"),
        ("3", "Database"),
        ("4", "Validation"),
        ("5", "Complete")
    ]

    progress_html = '<div class="progress-container"><div style="display: flex; justify-content: space-between; align-items: center;">'

    for i, (num, label) in enumerate(steps):
        step_num = i + 1
        if step_num < current_step:
            status_class = "step-completed"
            icon = "✓"
        elif step_num == current_step:
            status_class = "step-active"
            icon = num
        else:
            status_class = "step-pending"
            icon = num

        progress_html += f'''
<div class="progress-step">
    <div class="step-circle {status_class}">{icon}</div>
    <div style="margin-top: 0.5rem; font-size: 0.875rem; color: {"#667eea" if step_num == current_step else "#6b7280"};">
        {label}
    </div>
</div>
'''

    progress_html += '</div></div>'
    st.markdown(progress_html, unsafe_allow_html=True)


def render_step_1_welcome():
    """Step 1: Welcome and setup mode selection"""
    st.markdown("""
    <div class="main-header">
        <h1 style="margin: 0;">🚀 Welcome to Chat2Data</h1>
        <p style="font-size: 1.2rem; margin-top: 1rem; margin-bottom: 0;">
            Let's get you set up in just a few minutes
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Choose Your Setup Path")
    st.markdown("Select how you'd like to get started with Chat2Data:")

    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown("""
        <div class="setup-card">
            <h3>⚡ Quick Start</h3>
            <p>Get started immediately with our demo database and mock LLM provider.</p>
            <ul>
                <li>✅ Pre-configured demo database</li>
                <li>✅ Mock LLM (no API keys needed)</li>
                <li>✅ Sample data included</li>
                <li>✅ Ready in seconds</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

        if st.button("🚀 **Start with Demo**", key="quick_start_btn", use_container_width=True, type="primary"):
            set_setup_mode("quick_start")
            set_session_value("provider_type", "ollama")
            set_session_value("database_path", "./data/chat2data.db")
            set_onboarding_step(2)
            st.rerun()

    with col2:
        st.markdown("""
        <div class="setup-card">
            <h3>⚙️ Custom Setup</h3>
            <p>Connect your own database and configure your preferred LLM provider.</p>
            <ul>
                <li>📊 Connect your database</li>
                <li>🤖 Choose LLM provider</li>
                <li>🔧 Advanced configuration</li>
                <li>🔒 Full control</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

        if st.button("⚙️ **Custom Configuration**", key="custom_setup_btn", use_container_width=True):
            set_setup_mode("custom")
            set_onboarding_step(2)
            st.rerun()

    # Quick access for returning users
    st.markdown("---")
    col1, col2, col3 = st.columns([2, 1, 2])
    with col2:
        if st.button("Skip Setup →", key="skip_setup", help="Skip if already configured"):
            mark_onboarding_complete()
            st.switch_page("pages/1_🔍_Query.py")


def test_llm_provider():
    """Test LLM provider connection"""
    set_session_value("llm_test_status", "testing")

    try:
        provider_type = get_session_value("provider_type", "ollama")

        if provider_type == "mock":
            # Mock provider always succeeds
            time.sleep(0.5)  # Simulate test delay
            set_session_value("llm_test_status", "success")
            validation = get_session_value("validation_status", {})
            validation["llm_provider"] = True
            set_session_value("validation_status", validation)
            return True, "Mock LLM provider connected successfully!"
        else:
            # Test Ollama connection
            ollama_url = get_session_value("ollama_url", "http://localhost:11434")
            ollama_model = get_session_value("ollama_model", "llama3.2:latest")

            # Import and test Ollama
            from chat2data.providers.llm.ollama_provider import OllamaLLMProvider
            provider = OllamaLLMProvider(base_url=ollama_url, model=ollama_model)

            # Try a simple test
            test_result = asyncio.run(provider.generate_sql("test", []))

            if test_result:
                set_session_value("llm_test_status", "success")
                validation = get_session_value("validation_status", {})
                validation["llm_provider"] = True
                set_session_value("validation_status", validation)
                return True, f"Ollama ({ollama_model}) connected successfully!"
            else:
                raise Exception("No response from Ollama")

    except Exception as e:
        set_session_value("llm_test_status", "failed")
        return False, f"Connection failed: {str(e)}"


def render_step_2_llm():
    """Step 2: LLM Provider Configuration"""
    st.markdown("## 🤖 Configure LLM Provider")

    setup_mode = get_session_value("setup_mode")

    if setup_mode == "quick_start":
        # Quick start mode - auto configure
        st.info("✅ Using Mock LLM Provider (Pre-configured for demo)")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Provider", "Mock LLM")
        with col2:
            st.metric("Status", "Ready")
        with col3:
            st.metric("Cost", "Free")

        # Auto-proceed for quick start
        st.markdown("---")
        if st.button("Continue →", key="llm_continue", type="primary"):
            validation = get_session_value("validation_status", {})
            validation["llm_provider"] = True
            set_session_value("validation_status", validation)
            set_onboarding_step(3)
            st.rerun()

    else:
        # Custom setup mode
        st.markdown("Choose and configure your LLM provider:")

        provider = st.selectbox(
            "Select LLM Provider",
            options=["mock", "ollama"],
            format_func=lambda x: "Mock LLM (Testing)" if x == "mock" else "Ollama (Local)",
            key="setup_llm_provider"
        )

        if provider != get_session_value("provider_type"):
            set_session_value("provider_type", provider)
            set_session_value("llm_test_status", None)

        if provider == "ollama":
            col1, col2 = st.columns(2)

            with col1:
                ollama_url = st.text_input(
                    "Ollama URL",
                    value=get_session_value("ollama_url", "http://localhost:11434"),
                    key="setup_ollama_url",
                    help="URL where Ollama is running"
                )
                if ollama_url != get_session_value("ollama_url"):
                    set_session_value("ollama_url", ollama_url)
                    set_session_value("llm_test_status", None)

            with col2:
                ollama_model = st.text_input(
                    "Model Name",
                    value=get_session_value("ollama_model", "llama3.2:latest"),
                    key="setup_ollama_model",
                    help="Ollama model to use (e.g., llama2, codellama)"
                )
                if ollama_model != get_session_value("ollama_model"):
                    set_session_value("ollama_model", ollama_model)
                    set_session_value("llm_test_status", None)

            st.info("💡 Make sure Ollama is running: `ollama serve`")

        # Test connection button
        col1, col2, col3 = st.columns([1, 2, 1])

        with col2:
            test_status = get_session_value("llm_test_status")

            if test_status == "testing":
                st.info("⏳ Testing connection...")
                time.sleep(1)
                st.rerun()
            elif test_status == "success":
                st.success("✅ LLM Provider connected successfully!")
            elif test_status == "failed":
                st.error("❌ Connection failed. Please check your configuration.")

            if st.button("🔌 Test Connection", key="test_llm", use_container_width=True):
                success, message = test_llm_provider()
                if success:
                    st.success(message)
                else:
                    st.error(message)
                st.rerun()

        # Navigation
        st.markdown("---")
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("← Back", key="llm_back"):
                set_onboarding_step(1)
                st.rerun()

        with col3:
            validation = get_session_value("validation_status", {})
            if st.button(
                "Continue →",
                key="llm_next",
                type="primary" if validation.get("llm_provider") else "secondary",
                disabled=not validation.get("llm_provider")
            ):
                set_onboarding_step(3)
                st.rerun()


def test_database_connection():
    """Test database connection"""
    set_session_value("db_test_status", "testing")

    try:
        db_path = get_session_value("database_path", "./data/chat2data.db")

        # Test database connection
        db_provider = SQLiteDatabaseProvider(db_path)
        schema = db_provider.get_schema()

        if schema:
            set_session_value("db_test_status", "success")
            validation = get_session_value("validation_status", {})
            validation["database"] = True
            validation["schema_loaded"] = True
            set_session_value("validation_status", validation)

            table_count = len(schema)
            total_rows = sum(table.row_count for table in schema)
            return True, f"Connected! Found {table_count} tables with {total_rows:,} total rows"
        else:
            raise Exception("No schema found in database")

    except Exception as e:
        set_session_value("db_test_status", "failed")
        return False, f"Connection failed: {str(e)}"


def render_step_3_database():
    """Step 3: Database Configuration"""
    st.markdown("## 📊 Configure Database Connection")

    setup_mode = get_session_value("setup_mode")

    if setup_mode == "quick_start":
        # Quick start mode - use demo database
        st.info("✅ Using Demo Database (Pre-loaded with sample data)")

        # Show demo database info
        try:
            db_provider = SQLiteDatabaseProvider("./data/chat2data.db")
            schema = db_provider.get_schema()

            if schema:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Tables", len(schema))
                with col2:
                    total_rows = sum(table.row_count for table in schema)
                    st.metric("Total Records", f"{total_rows:,}")
                with col3:
                    st.metric("Database", "chat2data.db")

                # Show table list
                with st.expander("📋 View Tables"):
                    for table in schema:
                        st.text(f"• {table.name} ({table.row_count} rows)")
        except:
            st.warning("Demo database will be initialized")

        # Auto-proceed for quick start
        st.markdown("---")
        if st.button("Continue →", key="db_continue", type="primary"):
            validation = get_session_value("validation_status", {})
            validation["database"] = True
            validation["schema_loaded"] = True
            set_session_value("validation_status", validation)
            set_onboarding_step(4)
            st.rerun()

    else:
        # Custom setup mode
        st.markdown("Configure your database connection:")

        # Database type selector (for future expansion)
        db_type = st.selectbox(
            "Database Type",
            options=["sqlite"],
            format_func=lambda x: "SQLite" if x == "sqlite" else x.upper(),
            key="setup_db_type",
            help="Additional database types coming soon"
        )

        if db_type == "sqlite":
            db_path = st.text_input(
                "Database Path",
                value=get_session_value("database_path", "./data/chat2data.db"),
                key="setup_db_path",
                help="Path to your SQLite database file"
            )

            if db_path != get_session_value("database_path"):
                set_session_value("database_path", db_path)
                set_session_value("db_test_status", None)

            # Check if file exists
            if Path(db_path).exists():
                st.success(f"✅ File found: {db_path}")
            else:
                st.warning(f"⚠️ File not found: {db_path}")

        # Test connection
        col1, col2, col3 = st.columns([1, 2, 1])

        with col2:
            test_status = get_session_value("db_test_status")

            if test_status == "testing":
                st.info("⏳ Testing database connection...")
                time.sleep(1)
                st.rerun()
            elif test_status == "success":
                st.success("✅ Database connected successfully!")
            elif test_status == "failed":
                st.error("❌ Connection failed. Please check your database path.")

            if st.button("🔌 Test Connection", key="test_db", use_container_width=True):
                success, message = test_database_connection()
                if success:
                    st.success(message)

                    # Show schema preview
                    try:
                        db_provider = SQLiteDatabaseProvider(get_session_value("database_path"))
                        schema = db_provider.get_schema()
                        if schema:
                            with st.expander("📋 Database Schema"):
                                for table in schema:
                                    st.text(f"• {table.name} ({table.row_count} rows)")
                    except:
                        pass
                else:
                    st.error(message)
                st.rerun()

        # Navigation
        st.markdown("---")
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("← Back", key="db_back"):
                set_onboarding_step(2)
                st.rerun()

        with col3:
            validation = get_session_value("validation_status", {})
            if st.button(
                "Continue →",
                key="db_next",
                type="primary" if validation.get("database") else "secondary",
                disabled=not validation.get("database")
            ):
                set_onboarding_step(4)
                st.rerun()


def initialize_chat2data():
    """Initialize Chat2Data with configured settings"""
    try:
        provider_type = get_session_value("provider_type", "ollama")
        database_path = get_session_value("database_path", "./data/chat2data.db")

        # Create LLM provider and vector store
        if provider_type == "ollama":
            ollama_url = get_session_value("ollama_url", "http://localhost:11434")
            ollama_model = get_session_value("ollama_model", "llama3.2:latest")
            llm_provider = EnhancedOllamaLLMProvider(base_url=ollama_url, model=ollama_model)
            vector_store_provider = SemanticVectorStoreProvider(ollama_url, ollama_model)
        else:
            llm_provider = MockLLMProvider()
            vector_store_provider = MemoryVectorStoreProvider()

        # Create Enhanced Chat2Data instance
        use_enhanced = get_session_value("use_enhanced_mode", True)
        if use_enhanced:
            chat2data = EnhancedChat2Data(
                llm_provider=llm_provider,
                database_provider=SQLiteDatabaseProvider(database_path),
                vector_store_provider=vector_store_provider,
                use_smart_pipeline=True
            )
        else:
            chat2data = Chat2Data(
                llm_provider=llm_provider,
                database_provider=SQLiteDatabaseProvider(database_path),
                vector_store_provider=vector_store_provider
            )

        set_session_value("chat2data", chat2data)
        return True, "Chat2Data initialized successfully!"

    except Exception as e:
        return False, f"Initialization failed: {str(e)}"


def render_step_4_validation():
    """Step 4: Validation and Testing"""
    st.markdown("## ✅ Configuration Validation")

    st.markdown("Let's verify everything is working correctly:")

    validation = get_session_value("validation_status", {})

    # Show validation checklist
    checks = [
        ("LLM Provider", validation.get("llm_provider", False)),
        ("Database Connection", validation.get("database", False)),
        ("Schema Loaded", validation.get("schema_loaded", False)),
    ]

    col1, col2 = st.columns([2, 3])

    with col1:
        st.markdown("### Configuration Status")
        for check_name, is_valid in checks:
            if is_valid:
                st.markdown(f"✅ **{check_name}**")
            else:
                st.markdown(f"❌ {check_name}")

    with col2:
        st.markdown("### Test Query")

        # Initialize Chat2Data if not already done
        if not get_session_value("chat2data"):
            if st.button("🚀 Initialize Chat2Data", key="init_chat2data", use_container_width=True):
                success, message = initialize_chat2data()
                if success:
                    st.success(message)
                else:
                    st.error(message)
                st.rerun()
        else:
            st.success("✅ Chat2Data is initialized!")

            # Run a test query
            if st.button("🧪 Run Test Query", key="test_query", use_container_width=True):
                chat2data = get_session_value("chat2data")
                if chat2data:
                    with st.spinner("Running test query..."):
                        try:
                            result = asyncio.run(chat2data.query("Show me the first 3 rows from any table"))
                            if result and result.get("success"):
                                st.success("✅ Test query executed successfully!")
                                validation["test_query"] = True
                                set_session_value("validation_status", validation)

                                # Show results
                                if result.get("result", {}).get("data"):
                                    with st.expander("View Results"):
                                        st.json(result["result"]["data"][:3])
                            else:
                                st.error("Test query failed")
                        except Exception as e:
                            st.error(f"Test failed: {str(e)}")

    # Show configuration summary
    st.markdown("---")
    st.markdown("### 📋 Configuration Summary")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**LLM Provider:**")
        provider = get_session_value("provider_type", "ollama")
        if provider == "ollama":
            st.code(f"Ollama - {get_session_value('ollama_model', 'llama2')}")
        else:
            st.code("Mock LLM (Demo)")

    with col2:
        st.markdown("**Database:**")
        st.code(get_session_value("database_path", "./data/chat2data.db"))

    # Navigation
    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("← Back", key="val_back"):
            set_onboarding_step(3)
            st.rerun()

    with col3:
        all_valid = all(validation.get(k, False) for k in ["llm_provider", "database", "schema_loaded"])
        if st.button(
            "Complete Setup →",
            key="val_next",
            type="primary" if all_valid else "secondary",
            disabled=not all_valid
        ):
            set_onboarding_step(5)
            st.rerun()


def render_step_5_complete():
    """Step 5: Setup Complete"""
    st.markdown("""
    <div class="main-header">
        <h1 style="margin: 0;">🎉 Setup Complete!</h1>
        <p style="font-size: 1.2rem; margin-top: 1rem; margin-bottom: 0;">
            Chat2Data is ready to use
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.success("✅ All systems are configured and ready!")

    # Show what's next
    st.markdown("### 🚀 What's Next?")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div class="setup-card">
            <h4>🔍 Start Querying</h4>
            <p>Ask questions in natural language and get instant SQL results</p>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Open Query Interface", key="goto_query", use_container_width=True, type="primary"):
            mark_onboarding_complete()
            st.switch_page("pages/1_🔍_Query.py")

    with col2:
        st.markdown("""
        <div class="setup-card">
            <h4>📊 Explore Schema</h4>
            <p>Browse your database structure and understand your data</p>
        </div>
        """, unsafe_allow_html=True)

        if st.button("View Schema Explorer", key="goto_schema", use_container_width=True):
            mark_onboarding_complete()
            st.switch_page("pages/2_📊_Schema.py")

    with col3:
        st.markdown("""
        <div class="setup-card">
            <h4>⚙️ Adjust Settings</h4>
            <p>Fine-tune your configuration and preferences</p>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Open Settings", key="goto_settings", use_container_width=True):
            mark_onboarding_complete()
            st.switch_page("pages/3_⚙️_Settings.py")

    # Save configuration option
    st.markdown("---")
    st.markdown("### 💾 Save Configuration")

    col1, col2 = st.columns([3, 1])

    with col1:
        st.info("💡 Your configuration is automatically saved in the session. To persist it across restarts, you can export it.")

    with col2:
        config = {
            "provider_type": get_session_value("provider_type"),
            "database_path": get_session_value("database_path"),
            "ollama_url": get_session_value("ollama_url"),
            "ollama_model": get_session_value("ollama_model")
        }

        st.download_button(
            "📥 Export Config",
            data=json.dumps(config, indent=2),
            file_name="chat2data_config.json",
            mime="application/json",
            use_container_width=True
        )

    # Option to restart setup
    st.markdown("---")
    if st.button("🔄 Reconfigure", key="restart_setup"):
        reset_onboarding()
        st.rerun()


def main():
    """Main application logic"""

    # Get onboarding status
    status = get_onboarding_status()

    # If onboarding is complete and user has Chat2Data initialized, offer quick navigation
    if status['completed'] and get_session_value('chat2data'):
        # Show a mini header with quick navigation
        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

        with col1:
            st.markdown("### ✅ Chat2Data is configured")

        with col2:
            if st.button("🔍 Query", key="quick_query"):
                st.switch_page("pages/1_🔍_Query.py")

        with col3:
            if st.button("📊 Schema", key="quick_schema"):
                st.switch_page("pages/2_📊_Schema.py")

        with col4:
            if st.button("🔄 Reconfigure", key="quick_reconfig"):
                reset_onboarding()
                st.rerun()

        st.markdown("---")

        # Show configuration summary
        st.markdown("### Current Configuration")
        col1, col2 = st.columns(2)

        with col1:
            provider = get_session_value("provider_type", "ollama")
            st.metric("LLM Provider", f"Ollama ({get_session_value('ollama_model', 'llama2')})" if provider == "ollama" else "Mock")

        with col2:
            st.metric("Database", Path(get_session_value("database_path", "./data/chat2data.db")).name)

        return

    # Otherwise, show onboarding wizard
    current_step = status['step']

    # Render progress bar
    render_progress_bar(current_step)

    # Render current step
    if current_step == 1:
        render_step_1_welcome()
    elif current_step == 2:
        render_step_2_llm()
    elif current_step == 3:
        render_step_3_database()
    elif current_step == 4:
        render_step_4_validation()
    elif current_step == 5:
        render_step_5_complete()


# Sidebar for quick access (hidden during initial setup)
status = get_onboarding_status()
if status['completed']:
    with st.sidebar:
        st.header("🚀 Chat2Data")
        st.success("✅ Configuration Complete")

        if st.button("🔄 Reconfigure", key="sidebar_reconfig"):
            reset_onboarding()
            st.rerun()

        st.divider()

        st.markdown("### Quick Links")
        st.page_link("pages/1_🔍_Query.py", label="Query Interface")
        st.page_link("pages/2_📊_Schema.py", label="Schema Explorer")
        st.page_link("pages/3_⚙️_Settings.py", label="Settings")


if __name__ == "__main__":
    main()