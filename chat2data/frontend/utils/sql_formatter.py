"""SQL formatter utility for Chat2Data UI"""

import sqlparse
from typing import Optional


def format_sql(sql: str, reindent: bool = True, keyword_case: str = 'upper') -> str:
    """
    Format SQL query for better readability in the UI

    Args:
        sql: Raw SQL query string
        reindent: Whether to reindent the SQL
        keyword_case: Case for keywords ('upper', 'lower', 'capitalize')

    Returns:
        Formatted SQL query string
    """
    if not sql or not sql.strip():
        return sql

    try:
        # Format the SQL with sqlparse
        formatted = sqlparse.format(
            sql,
            reindent=reindent,
            keyword_case=keyword_case,
            indent_width=2,
            indent_after_first=False,
            use_space_around_operators=True,
            comma_first=False,
            strip_comments=False
        )

        # Additional formatting for better CTE handling
        formatted = _improve_cte_formatting(formatted)

        return formatted.strip()

    except Exception as e:
        # If formatting fails, return the original SQL
        print(f"SQL formatting error: {e}")
        return sql


def _improve_cte_formatting(sql: str) -> str:
    """
    Improve formatting specifically for CTEs (WITH clauses)

    Args:
        sql: SQL query string

    Returns:
        SQL with improved CTE formatting
    """
    lines = sql.split('\n')
    improved_lines = []
    in_cte = False
    cte_depth = 0

    for line in lines:
        stripped = line.strip()
        upper_stripped = stripped.upper()

        # Check if we're starting a CTE
        if upper_stripped.startswith('WITH '):
            in_cte = True
            improved_lines.append(line)
        # Check for CTE definition
        elif in_cte and ' AS (' in upper_stripped:
            # Ensure proper formatting for CTE AS clause
            if 'AS(' in line.replace(' ', ''):
                # Add space between AS and (
                line = line.replace('AS(', 'AS (')
            improved_lines.append(line)
            cte_depth += 1
        # Handle closing parentheses of CTEs
        elif in_cte and stripped == ')':
            cte_depth -= 1
            improved_lines.append(line)
            if cte_depth == 0:
                in_cte = False
        # Handle multiple CTEs separated by comma
        elif in_cte and cte_depth == 0 and stripped.startswith(','):
            improved_lines.append(line)
            in_cte = True
        else:
            improved_lines.append(line)

    return '\n'.join(improved_lines)


def format_sql_compact(sql: str) -> str:
    """
    Format SQL in a more compact way, suitable for simpler queries

    Args:
        sql: Raw SQL query string

    Returns:
        Formatted SQL query string (compact version)
    """
    if not sql or not sql.strip():
        return sql

    try:
        # Format with less aggressive indentation
        formatted = sqlparse.format(
            sql,
            reindent=True,
            keyword_case='upper',
            indent_width=2,
            indent_after_first=False,
            use_space_around_operators=True,
            wrap_after=80,  # Wrap long lines
            comma_first=False
        )

        return formatted.strip()

    except Exception:
        return sql


def is_complex_query(sql: str) -> bool:
    """
    Check if a query is complex (has CTEs, multiple JOINs, subqueries, etc.)

    Args:
        sql: SQL query string

    Returns:
        True if the query is complex, False otherwise
    """
    if not sql:
        return False

    upper_sql = sql.upper()

    # Check for complexity indicators
    complex_indicators = [
        'WITH ',  # CTEs
        upper_sql.count('JOIN') >= 2,  # Multiple JOINs
        'SELECT' in upper_sql[upper_sql.find('FROM'):] if 'FROM' in upper_sql else False,  # Subqueries
        upper_sql.count('SELECT') > 1,  # Multiple SELECT statements
        'UNION' in upper_sql,
        'INTERSECT' in upper_sql,
        'EXCEPT' in upper_sql,
        'CASE WHEN' in upper_sql
    ]

    return any(complex_indicators)


def format_sql_auto(sql: str) -> str:
    """
    Automatically choose the best formatting based on query complexity

    Args:
        sql: Raw SQL query string

    Returns:
        Formatted SQL query string
    """
    if is_complex_query(sql):
        return format_sql(sql)
    else:
        return format_sql_compact(sql)