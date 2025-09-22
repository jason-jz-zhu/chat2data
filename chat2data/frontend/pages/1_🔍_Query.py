"""
Query Interface Page - Main interface for natural language queries
"""

import streamlit as st
import asyncio
import pandas as pd
import json
import time
import uuid
from pathlib import Path
import sys

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from chat2data import Chat2Data
from chat2data.core.enhanced_chat2data import EnhancedChat2Data
from chat2data.providers.llm.mock_provider import MockLLMProvider
from chat2data.providers.llm.enhanced_ollama_provider import EnhancedOllamaLLMProvider
from chat2data.providers.database.sqlite_provider import SQLiteDatabaseProvider
from chat2data.providers.vector.memory_provider import MemoryVectorStoreProvider
from chat2data.providers.vector.semantic_provider import SemanticVectorStoreProvider
from chat2data.frontend.utils import (
    init_session_state, get_session_value, get_chat2data,
    start_query_processing, end_query_processing,
    is_query_processing, should_skip_historical_render,
    has_sql_been_rendered, mark_sql_as_rendered,
    clear_rendered_sql_queries, format_sql_auto
)

# Initialize session state
init_session_state()

def generate_dynamic_examples(chat2data_instance):
    """Generate dynamic example queries based on the actual database schema"""
    try:
        # Get schema information
        schema = chat2data_instance.get_schema()
        if not schema:
            # Fallback to generic examples
            return [
                "Show me all data from the main table",
                "Count all records",
                "Show the first 10 records",
                "What columns are available?",
                "Display table information"
            ]

        examples = []
        table_names = [table.name for table in schema]

        # Basic listing queries for each table
        for table in table_names[:3]:  # Limit to first 3 tables
            examples.append(f"Show me all {table}")
            examples.append(f"Count all {table}")

        # Generic aggregation examples
        examples.extend([
            f"What are the top 5 records from {table_names[0]}?",
            f"Show the first 10 entries from {table_names[0]}",
        ])

        # Try to find numeric columns for aggregation examples
        for table in schema[:2]:  # Check first 2 tables
            numeric_cols = []
            for col in table.columns:
                col_name = col.name if hasattr(col, 'name') else str(col)
                if any(keyword in col_name.lower() for keyword in ['price', 'amount', 'cost', 'value', 'quantity', 'count', 'total']):
                    examples.append(f"Show average {col_name} from {table.name}")
                    examples.append(f"What is the total {col_name}?")
                    break  # One example per table

        # If we have multiple tables, add join examples
        if len(table_names) > 1:
            examples.append(f"Show {table_names[0]} with related {table_names[1]}")

        # Limit to 7 examples to match the original
        return examples[:7] if examples else [
            "Show all data",
            "Count records",
            "Display information",
            "What data is available?",
            "Show table structure"
        ]

    except Exception as e:
        # Fallback to generic examples if anything fails
        return [
            "Show all data",
            "Count records",
            "Display the first 10 rows",
            "What tables are available?",
            "Show data summary"
        ]

def get_or_create_chat2data():
    """Get existing or create Enhanced Chat2Data instance"""
    # Try to get existing instance from session state
    existing = get_chat2data()
    if existing:
        return existing

    # Create new instance if none exists
    if st.session_state.chat2data is None:
        provider_type = st.session_state.get('provider_type', 'ollama')
        database_path = st.session_state.get('database_path', './data/chat2data.db')
        use_enhanced = st.session_state.get('use_enhanced_mode', True)

        # Create LLM provider
        if provider_type == 'mock':
            llm_provider = MockLLMProvider()
        else:
            ollama_url = st.session_state.get('ollama_url', 'http://localhost:11434')
            ollama_model = st.session_state.get('ollama_model', 'llama3.2:latest')
            llm_provider = EnhancedOllamaLLMProvider(
                model_name=ollama_model,
                base_url=ollama_url
            )

        # Create vector store (use semantic if available)
        if provider_type != 'mock':
            vector_store = SemanticVectorStoreProvider(
                ollama_base_url=ollama_url,
                embedding_model=ollama_model
            )
        else:
            vector_store = MemoryVectorStoreProvider()

        # Use enhanced or regular Chat2Data
        if use_enhanced:
            st.session_state.chat2data = EnhancedChat2Data(
                llm_provider=llm_provider,
                database_provider=SQLiteDatabaseProvider(database_path),
                vector_store_provider=vector_store,
                use_smart_pipeline=True
            )
        else:
            st.session_state.chat2data = Chat2Data(
                llm_provider=llm_provider,
                database_provider=SQLiteDatabaseProvider(database_path),
                vector_store_provider=vector_store
            )

    return st.session_state.chat2data

def display_result_as_table(data):
    """Display result as a table"""
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)
        return df
    return None

def display_result_as_chart(data, message_idx="current"):
    """Display result as a chart with stable widget keys"""
    if not data or len(data) == 0:
        st.info("No data to visualize")
        return

    df = pd.DataFrame(data)

    if len(df.columns) < 2:
        st.info("Need at least 2 columns for visualization")
        return

    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    non_numeric_cols = df.select_dtypes(exclude=['number']).columns.tolist()

    if numeric_cols:
        col1, col2, col3 = st.columns(3)

        # Use stable message-based keys for widgets
        with col1:
            chart_type = st.selectbox("Chart Type", ["bar", "line", "area", "scatter"], key=f"chart_type_{message_idx}")

        with col2:
            if non_numeric_cols:
                x_axis = st.selectbox("X-axis", non_numeric_cols, key=f"x_axis_{message_idx}")
            else:
                x_axis = st.selectbox("X-axis", df.columns.tolist(), key=f"x_axis_all_{message_idx}")

        with col3:
            y_axis = st.selectbox("Y-axis", numeric_cols, key=f"y_axis_{message_idx}")

        try:
            if chart_type == "bar":
                st.bar_chart(df.set_index(x_axis)[y_axis] if x_axis != y_axis else df[y_axis])
            elif chart_type == "line":
                st.line_chart(df.set_index(x_axis)[y_axis] if x_axis != y_axis else df[y_axis])
            elif chart_type == "area":
                st.area_chart(df.set_index(x_axis)[y_axis] if x_axis != y_axis else df[y_axis])
            else:
                if x_axis in numeric_cols and y_axis in numeric_cols:
                    st.scatter_chart(df[[x_axis, y_axis]].set_index(x_axis))
                else:
                    st.info("Scatter chart requires numeric columns for both axes")
        except Exception as e:
            st.error(f"Error creating chart: {str(e)}")
    else:
        st.info("No numeric columns available for visualization")

def main():
    st.title("🔍 Query Interface")
    st.markdown("Ask questions about your data in natural language")

    # Initialize Chat2Data
    chat2data = get_or_create_chat2data()

    if not chat2data:
        st.error("Chat2Data not initialized. Please check configuration.")
        return

    # Chat interface
    st.markdown("### 💬 Chat with your data")

    # Display chat history
    for idx, message in enumerate(st.session_state.chat_messages):
        # Skip rendering historical assistant messages that are currently being processed
        if (message["role"] == "assistant" and
            "id" in message and
            should_skip_historical_render(message["id"])):
            continue

        with st.chat_message(message["role"]):
            if message["role"] == "user":
                st.write(message["content"])
            else:
                # Assistant message with result
                if "sql" in message:
                    confidence_text = f" (Confidence: {message.get('confidence', 0):.0%})" if 'confidence' in message else ""
                    with st.expander(f"🔍 Generated SQL{confidence_text}"):
                        formatted_sql = format_sql_auto(message["sql"])
                        st.code(formatted_sql, language="sql")

                if "summary" in message:
                    st.info(f"📊 {message['summary']}")

                if "data" in message:
                    if message["data"]:
                        st.write(f"Found {len(message['data'])} results")

                        # Create tabs for different views
                        tabs = st.tabs(["📊 Table", "📈 Chart", "📝 JSON"])

                        with tabs[0]:
                            display_result_as_table(message["data"])

                        with tabs[1]:
                            display_result_as_chart(message["data"], message_idx=f"msg_{idx}")

                        with tabs[2]:
                            st.json(message["data"])
                    else:
                        st.info("No results found")

                if "error" in message:
                    st.error(message["error"])

    # Always create the chat input so it's always visible
    chat_prompt = st.chat_input("Ask a question about your data...")

    # Check if we need to execute a query from example buttons
    execute_from_button = False
    prompt = None

    if 'execute_query' in st.session_state and st.session_state.execute_query:
        prompt = st.session_state.execute_query
        st.session_state.execute_query = None  # Clear the flag
        execute_from_button = True
    elif chat_prompt:
        prompt = chat_prompt

    # Process query
    if prompt:
        # Generate unique query ID
        query_id = str(uuid.uuid4())

        # Mark query processing started
        start_query_processing(query_id)

        # Add user message and display it only if from chat input (not from button)
        if not execute_from_button:
            st.session_state.chat_messages.append({
                "role": "user",
                "content": prompt,
                "id": query_id + "_user"
            })
            with st.chat_message("user"):
                st.write(prompt)

        # Get assistant response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    # Execute query
                    result = asyncio.run(chat2data.query(prompt))

                    if result['success']:
                        assistant_message = {
                            "role": "assistant",
                            "id": query_id,
                            "sql": result['sql'],
                            "data": result['result'].get('data', []) if result['result']['success'] else [],
                        }

                        # Add confidence score if available
                        if 'confidence' in result:
                            assistant_message['confidence'] = result['confidence']

                        # Add summary if available
                        if 'summary' in result and result['summary']:
                            assistant_message['summary'] = result['summary']

                        if not result['result']['success']:
                            assistant_message["error"] = result['result'].get('error', 'Query failed')

                        # Display the SQL query in the live response
                        if 'sql' in result:
                            confidence_text = f" (Confidence: {result.get('confidence', 0):.0%})" if 'confidence' in result else ""
                            with st.expander(f"🔍 Generated SQL{confidence_text}"):
                                formatted_sql = format_sql_auto(result['sql'])
                                st.code(formatted_sql, language="sql")

                        # Show summary if available
                        if 'summary' in result and result['summary']:
                            st.info(f"📊 {result['summary']}")

                        # Display results
                        if result['result']['success']:
                            data = result['result'].get('data', [])
                            if data:
                                st.write(f"Found {len(data)} results")

                                tabs = st.tabs(["📊 Table", "📈 Chart", "📝 JSON"])

                                with tabs[0]:
                                    df = display_result_as_table(data)

                                with tabs[1]:
                                    display_result_as_chart(data, message_idx="current")

                                with tabs[2]:
                                    st.json(data)

                                # Export options
                                with st.expander("💾 Export Results"):
                                    col1, col2, col3 = st.columns(3)

                                    with col1:
                                        if df is not None:
                                            csv = df.to_csv(index=False)
                                            st.download_button(
                                                "📥 Download CSV",
                                                data=csv,
                                                file_name="results.csv",
                                                mime="text/csv",
                                                key=f"query_export_csv_{len(st.session_state.chat_messages)}_{int(time.time() * 1000)}"
                                            )

                                    with col2:
                                        json_str = json.dumps(data, indent=2)
                                        st.download_button(
                                            "📥 Download JSON",
                                            data=json_str,
                                            file_name="results.json",
                                            mime="application/json",
                                            key=f"query_export_json_{len(st.session_state.chat_messages)}_{int(time.time() * 1000)}"
                                        )

                                    with col3:
                                        st.download_button(
                                            "📥 Download SQL",
                                            data=result['sql'],
                                            file_name="query.sql",
                                            mime="text/plain",
                                            key=f"query_export_sql_{len(st.session_state.chat_messages)}_{int(time.time() * 1000)}"
                                        )
                            else:
                                st.info("No results found")
                                assistant_message["data"] = []
                        else:
                            error_msg = result['result'].get('error', 'Query failed')
                            st.error(error_msg)
                            assistant_message["error"] = error_msg

                    else:
                        error_msg = result.get('error', 'Unknown error')
                        st.error(error_msg)
                        assistant_message = {
                            "role": "assistant",
                            "id": query_id,
                            "error": error_msg
                        }

                    st.session_state.chat_messages.append(assistant_message)

                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    st.error(error_msg)
                    st.session_state.chat_messages.append({
                        "role": "assistant",
                        "id": query_id,
                        "error": error_msg
                    })
                finally:
                    # Mark query processing ended
                    end_query_processing(query_id)

    # Sidebar with quick actions
    with st.sidebar:
        st.markdown("### 🚀 Quick Actions")

        if st.button("🗑️ Clear Chat History", key="clear_chat_history"):
            st.session_state.chat_messages = []
            # Clear any execute_query flag that might be lingering
            if 'execute_query' in st.session_state:
                del st.session_state.execute_query
            # Clear rendered SQL queries tracking
            clear_rendered_sql_queries()
            st.rerun()

        st.markdown("### 💡 Example Queries")

        # Generate dynamic examples based on current schema
        chat2data = get_or_create_chat2data()
        if chat2data:
            example_queries = generate_dynamic_examples(chat2data)
        else:
            # Fallback to generic examples if no Chat2Data instance
            example_queries = [
                "Show all available data",
                "Count total records",
                "Display table structure",
                "What data is available?",
                "Show the first 10 rows"
            ]

        for query in example_queries:
            if st.button(query, key=f"eq_{query}"):
                # Generate query ID for the example
                example_query_id = str(uuid.uuid4())
                # Add to chat and execute immediately
                st.session_state.chat_messages.append({
                    "role": "user",
                    "content": query,
                    "id": example_query_id + "_user"
                })
                # Set a flag to trigger query execution
                st.session_state['execute_query'] = query
                st.rerun()

if __name__ == "__main__":
    main()