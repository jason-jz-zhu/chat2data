"""Frontend utilities for Chat2Data Streamlit application"""

from .session_manager import (
    init_session_state,
    get_session_value,
    set_session_value,
    ensure_chat2data_initialized,
    clear_session_state,
    get_chat2data,
    requires_chat2data,
    start_query_processing,
    end_query_processing,
    is_query_processing,
    get_current_query_id,
    should_skip_historical_render,
    has_sql_been_rendered,
    mark_sql_as_rendered,
    clear_rendered_sql_queries
)

from .sql_formatter import (
    format_sql,
    format_sql_compact,
    format_sql_auto,
    is_complex_query
)

__all__ = [
    'init_session_state',
    'get_session_value',
    'set_session_value',
    'ensure_chat2data_initialized',
    'clear_session_state',
    'get_chat2data',
    'requires_chat2data',
    'start_query_processing',
    'end_query_processing',
    'is_query_processing',
    'get_current_query_id',
    'should_skip_historical_render',
    'has_sql_been_rendered',
    'mark_sql_as_rendered',
    'clear_rendered_sql_queries',
    'format_sql',
    'format_sql_compact',
    'format_sql_auto',
    'is_complex_query'
]