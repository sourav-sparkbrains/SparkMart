from typing import TypedDict

class RecommendationState(TypedDict):
    """State that flows through the graph"""
    user_query: str
    session_id: str

    available_columns: list
    available_categories: list
    sample_products: list

    sql_query: str

    validation_errors: list
    query_results: list

    formatted_response: str
    error_message: str