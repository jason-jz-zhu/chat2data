"""
Schema Explorer Page - Browse and understand database structure
"""

import streamlit as st
import pandas as pd
import asyncio
from pathlib import Path
import sys

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from chat2data import Chat2Data
from chat2data.providers.llm.mock_provider import MockLLMProvider
from chat2data.providers.database.sqlite_provider import SQLiteDatabaseProvider
from chat2data.providers.vector.memory_provider import MemoryVectorStoreProvider

def get_chat2data():
    """Get or create Chat2Data instance"""
    if 'chat2data' not in st.session_state or st.session_state.chat2data is None:
        provider_type = st.session_state.get('provider_type', 'mock')
        database_path = st.session_state.get('database_path', './data/chat2data.db')

        if provider_type == 'mock':
            llm_provider = MockLLMProvider()
        else:
            from chat2data.providers.llm.ollama_provider import OllamaLLMProvider
            llm_provider = OllamaLLMProvider()

        st.session_state.chat2data = Chat2Data(
            llm_provider=llm_provider,
            database_provider=SQLiteDatabaseProvider(database_path),
            vector_store_provider=MemoryVectorStoreProvider()
        )

    return st.session_state.chat2data

def get_sample_data(chat2data, table_name, limit=5):
    """Get sample data from a table"""
    try:
        query = f"SELECT * FROM {table_name} LIMIT {limit}"
        result = asyncio.run(chat2data.query(f"Show me the first {limit} rows from {table_name}"))

        if result['success'] and result['result']['success']:
            return result['result'].get('data', [])
    except:
        pass
    return []

def main():
    st.title("📊 Database Schema Explorer")
    st.markdown("Explore your database structure and relationships")

    # Initialize Chat2Data
    chat2data = get_chat2data()

    if not chat2data:
        st.error("Chat2Data not initialized. Please check configuration.")
        return

    # Get schema
    schema = chat2data.get_schema()

    if not schema:
        st.warning("No schema information available")
        return

    # Summary section
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Tables", len(schema))

    with col2:
        total_columns = sum(len(table.columns) for table in schema)
        st.metric("Total Columns", total_columns)

    with col3:
        total_rows = sum(table.row_count for table in schema)
        st.metric("Total Rows", f"{total_rows:,}")

    with col4:
        db_path = st.session_state.get('database_path', 'N/A')
        st.metric("Database", db_path.split('/')[-1])

    st.divider()

    # Table selector
    table_names = [table.name for table in schema]
    selected_table = st.selectbox(
        "Select a table to explore:",
        table_names,
        key="schema_table_selector",
        help="Choose a table to view its structure and sample data"
    )

    # Find selected table schema
    table_schema = next((table for table in schema if table.name == selected_table), None)

    if table_schema:
        # Table information
        st.markdown(f"### 📁 Table: **{table_schema.name}**")

        col1, col2 = st.columns([1, 2])

        with col1:
            st.metric("Rows", f"{table_schema.row_count:,}")
            st.metric("Columns", len(table_schema.columns))

        with col2:
            # Column information
            st.markdown("#### 📋 Columns")

            columns_data = []
            for col in table_schema.columns:
                if isinstance(col, dict):
                    columns_data.append({
                        "Column Name": col.get('name', 'Unknown'),
                        "Data Type": col.get('type', 'Unknown'),
                        "Nullable": "Yes" if col.get('nullable', True) else "No",
                        "Primary Key": "Yes" if col.get('primary_key', False) else "No"
                    })
                else:
                    columns_data.append({
                        "Column Name": col,
                        "Data Type": "Unknown",
                        "Nullable": "Unknown",
                        "Primary Key": "Unknown"
                    })

            df_columns = pd.DataFrame(columns_data)
            st.dataframe(df_columns, use_container_width=True, hide_index=True)

        # Sample data section
        st.markdown("#### 🔍 Sample Data")

        # Handle tables with different row counts
        if table_schema.row_count == 0:
            st.info("This table is empty.")
        else:
            # Calculate appropriate slider bounds
            min_rows = 1
            max_rows = min(100, table_schema.row_count)
            default_value = min(10, table_schema.row_count)

            # Adjust step size based on row count
            if table_schema.row_count <= 10:
                step_size = 1
            elif table_schema.row_count <= 50:
                step_size = 5
            else:
                step_size = 10

            sample_size = st.slider(
                "Number of sample rows:",
                min_value=min_rows,
                max_value=max_rows,
                value=default_value,
                step=step_size,
                key=f"sample_size_slider_{selected_table}"
            )

            if st.button(f"Load {sample_size} Sample Rows", key=f"load_sample_{selected_table}"):
                with st.spinner(f"Loading sample data from {selected_table}..."):
                    sample_data = get_sample_data(chat2data, selected_table, sample_size)

                    if sample_data:
                        df_sample = pd.DataFrame(sample_data)
                        st.dataframe(df_sample, use_container_width=True)

                        # Statistics for numeric columns
                        numeric_cols = df_sample.select_dtypes(include=['number']).columns

                        if len(numeric_cols) > 0:
                            st.markdown("##### 📈 Numeric Column Statistics")
                            st.dataframe(df_sample[numeric_cols].describe(), use_container_width=True)

                        # Export sample data
                        csv = df_sample.to_csv(index=False)
                        st.download_button(
                            "📥 Download Sample Data (CSV)",
                            data=csv,
                            file_name=f"{selected_table}_sample.csv",
                            mime="text/csv",
                            key=f"download_csv_{selected_table}"
                        )
                    else:
                        st.warning(f"No sample data available for {selected_table}")

    # Schema diagram section
    with st.expander("🔗 Database Relationships"):
        st.markdown("### Entity Relationship Diagram")

        # Create a dynamic text-based representation based on actual schema
        if schema:
            table_names = [table.name for table in schema]
            if len(table_names) > 1:
                # Generate a simple relationship diagram
                diagram_text = "Database Structure:\n\n"
                for i, table in enumerate(table_names[:4]):  # Show up to 4 tables
                    diagram_text += f"        {table.title()}"
                    if i < len(table_names) - 1:
                        diagram_text += " ──── "
                    diagram_text += "\n"
                st.code(diagram_text)
            else:
                st.code(f"        Single Table: {table_names[0] if table_names else 'No tables found'}")

            # Discover relationships dynamically
            relationships = []
            for table in schema:
                for column in table.columns:
                    col_name = column.name if hasattr(column, 'name') else str(column)
                    # Look for foreign key patterns (column names ending with _id)
                    if col_name.lower().endswith('_id') and col_name.lower() != 'id':
                        # Try to find the referenced table
                        base_name = col_name[:-3]  # Remove _id suffix
                        for potential_table in table_names:
                            if base_name.lower() in potential_table.lower() or potential_table.lower() in base_name.lower():
                                relationships.append(f"**{table.name}.{col_name}** → {potential_table}.id")
                                break

            if relationships:
                st.info("Discovered Relationships:")
                st.markdown("- " + "\n- ".join(relationships))
            else:
                st.info("No foreign key relationships detected. Relationships may exist but not follow standard naming patterns.")
        else:
            st.warning("No schema information available. Please ensure database is connected and accessible.")

    # Schema search
    with st.expander("🔍 Search Schema"):
        search_term = st.text_input("Search for column or table names:", key="schema_search_input")

        if search_term:
            search_lower = search_term.lower()
            results = []

            for table in schema:
                # Check table name
                if search_lower in table.name.lower():
                    results.append(f"**Table**: {table.name}")

                # Check column names
                for col in table.columns:
                    col_name = col.get('name', col) if isinstance(col, dict) else col
                    if search_lower in str(col_name).lower():
                        results.append(f"**Column**: {table.name}.{col_name}")

            if results:
                st.markdown("### Search Results:")
                for result in results:
                    st.markdown(f"- {result}")
            else:
                st.info(f"No results found for '{search_term}'")

    # Quick insights
    with st.expander("💡 Quick Insights"):
        st.markdown("### Database Overview")

        # Table sizes
        st.markdown("#### Table Sizes")
        table_sizes = pd.DataFrame([
            {"Table": table.name, "Rows": table.row_count, "Columns": len(table.columns)}
            for table in schema
        ])
        table_sizes = table_sizes.sort_values("Rows", ascending=False)

        col1, col2 = st.columns(2)

        with col1:
            st.bar_chart(table_sizes.set_index("Table")["Rows"])

        with col2:
            st.dataframe(table_sizes, use_container_width=True, hide_index=True)

        # Largest tables
        st.markdown("#### Largest Tables")
        largest_tables = table_sizes.head(3)
        for _, row in largest_tables.iterrows():
            st.info(f"**{row['Table']}**: {row['Rows']:,} rows, {row['Columns']} columns")

if __name__ == "__main__":
    main()