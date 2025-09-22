"""
Session State Manager for Streamlit Chat2Data Application
Provides centralized session state management for all pages
"""

import streamlit as st
from typing import Any, Optional
from ...config.central_config import get_config


def init_session_state():
    """Initialize all session state variables with defaults from central configuration"""
    config = get_config()
    ui_defaults = config.get_ui_defaults()

    defaults = {
        'chat2data': None,
        'query_history': [],
        'current_result': None,
        'show_sql': False,
        'provider_type': ui_defaults['provider_type'],
        'database_path': ui_defaults['database_path'],
        'selected_example': None,
        'auto_execute_example': False,
        'cached_schema': None,
        'ollama_url': ui_defaults['ollama_url'],
        'ollama_model': ui_defaults['ollama_model'],
        'chat_messages': [],
        'export_format': 'None',
        # Query processing state tracking
        'processing_query': False,  # Flag to indicate if a query is being processed
        'current_query_id': None,  # Unique ID for the current query being processed
        'last_processed_query_id': None,  # ID of the last successfully processed query
        'rendered_sql_queries': set(),  # Track which SQL queries have been rendered to prevent duplicates
        # Onboarding related states
        'onboarding_completed': False,
        'setup_mode': None,  # 'quick_start' or 'custom'
        'setup_step': 1,  # Current wizard step (1-5)
        'validation_status': {
            'llm_provider': False,
            'database': False,
            'schema_loaded': False,
            'test_query': False
        },
        'llm_test_status': None,  # 'testing', 'success', 'failed', None
        'db_test_status': None,  # 'testing', 'success', 'failed', None
    }

    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value


def get_session_value(key: str, default: Any = None) -> Any:
    """
    Safely get a value from session state with default fallback

    Args:
        key: The session state key to retrieve
        default: Default value if key doesn't exist

    Returns:
        The session state value or default
    """
    return st.session_state.get(key, default)


def set_session_value(key: str, value: Any):
    """
    Safely set a value in session state

    Args:
        key: The session state key to set
        value: The value to set
    """
    st.session_state[key] = value


def ensure_chat2data_initialized() -> bool:
    """
    Check if Chat2Data is initialized

    Returns:
        True if initialized, False otherwise
    """
    return get_session_value('chat2data') is not None


def clear_session_state():
    """Clear all session state variables"""
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def get_chat2data():
    """
    Get the Chat2Data instance from session state
    Returns None if not initialized
    """
    return get_session_value('chat2data')


def requires_chat2data(func):
    """
    Decorator to ensure Chat2Data is initialized before running a function
    """
    def wrapper(*args, **kwargs):
        if not ensure_chat2data_initialized():
            st.error("Chat2Data is not initialized. Please initialize from the Configuration sidebar.")
            return None
        return func(*args, **kwargs)
    return wrapper


def get_onboarding_status() -> dict:
    """
    Get the current onboarding status

    Returns:
        Dictionary with onboarding status information
    """
    return {
        'completed': get_session_value('onboarding_completed', False),
        'mode': get_session_value('setup_mode'),
        'step': get_session_value('setup_step', 1),
        'validation': get_session_value('validation_status', {})
    }


def set_onboarding_step(step: int):
    """Set the current onboarding step"""
    set_session_value('setup_step', step)


def set_setup_mode(mode: str):
    """Set the setup mode (quick_start or custom)"""
    set_session_value('setup_mode', mode)


def mark_onboarding_complete():
    """Mark onboarding as completed"""
    set_session_value('onboarding_completed', True)


def reset_onboarding():
    """Reset onboarding to start over"""
    set_session_value('onboarding_completed', False)
    set_session_value('setup_mode', None)
    set_session_value('setup_step', 1)
    set_session_value('validation_status', {
        'llm_provider': False,
        'database': False,
        'schema_loaded': False,
        'test_query': False
    })
    set_session_value('llm_test_status', None)
    set_session_value('db_test_status', None)


def start_query_processing(query_id: str):
    """
    Mark the start of query processing

    Args:
        query_id: Unique identifier for the query being processed
    """
    set_session_value('processing_query', True)
    set_session_value('current_query_id', query_id)


def end_query_processing(query_id: str):
    """
    Mark the end of query processing

    Args:
        query_id: Unique identifier for the query that finished processing
    """
    if get_session_value('current_query_id') == query_id:
        set_session_value('processing_query', False)
        set_session_value('last_processed_query_id', query_id)
        set_session_value('current_query_id', None)


def is_query_processing() -> bool:
    """Check if a query is currently being processed"""
    return get_session_value('processing_query', False)


def get_current_query_id() -> Optional[str]:
    """Get the ID of the currently processing query"""
    return get_session_value('current_query_id')


def should_skip_historical_render(message_id: str) -> bool:
    """
    Check if a historical message should skip rendering to avoid duplicates

    Args:
        message_id: ID of the historical message

    Returns:
        True if the message should be skipped (it's currently being processed)
    """
    return (is_query_processing() and
            get_current_query_id() == message_id)


def has_sql_been_rendered(query_id: str) -> bool:
    """
    Check if an SQL query has already been rendered

    Args:
        query_id: Unique identifier for the query

    Returns:
        True if the SQL has already been rendered
    """
    rendered_queries = get_session_value('rendered_sql_queries', set())
    return query_id in rendered_queries


def mark_sql_as_rendered(query_id: str):
    """
    Mark an SQL query as having been rendered

    Args:
        query_id: Unique identifier for the query
    """
    if 'rendered_sql_queries' not in st.session_state:
        st.session_state.rendered_sql_queries = set()
    st.session_state.rendered_sql_queries.add(query_id)


def clear_rendered_sql_queries():
    """Clear the set of rendered SQL queries"""
    set_session_value('rendered_sql_queries', set())