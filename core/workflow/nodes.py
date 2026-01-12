import logging
import re
from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy import text, inspect

from common.llm import groq_model, gemini_model
from db.database import engine
from core.prompts.prompts import INTENT_DETECTION_PROMPT,QUERY_GENERATOR_PROMPT,RESPONSE_FORMATTER_PROMPT
from core.workflow.schema import RecommendationState

logger = logging.getLogger(__name__)

def intent_detector_node(state: RecommendationState) -> RecommendationState:
    """
    Converts vague user queries into a clear, structured intent form.
    Overwrites state['user_query'] with a cleaned version.
    Extracts:
      - intent (semantic_search, category_browse, product_lookup, follow_up)
      - keywords (list)
    Then forwards the updated user_query to the next node.
    """

    logger.info("[INTENT_DETECTOR] Analyzing user intent...")

    raw_query = state.get("user_query", "")

    prompt = ChatPromptTemplate.from_messages([
        ("system", INTENT_DETECTION_PROMPT),
        ("human", f"User Query: {raw_query}\nReturn JSON:")
    ])

    try:
        chain = prompt | gemini_model
        response = chain.invoke({})
        content = response.content.strip()

        import json
        data = json.loads(content)

        state["user_query"] = data.get("clean_query", raw_query)

        logger.info(f"[INTENT_DETECTOR] Clean Query: {state['user_query']}")

    except Exception as e:
        logger.error(f"[INTENT_DETECTOR] Error: {e}")
        state["user_query"] = raw_query

    return state


def inspect_schema_node(state: RecommendationState) -> RecommendationState:
    """
    Fetches actual database schema and sample data
    """
    logger.info("[SCHEMA_INSPECTOR] Fetching database schema...")

    try:
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('Ecommerce_Data')]
        state["available_columns"] = columns

        with engine.connect() as conn:
            result = conn.execute(text("SELECT DISTINCT Category FROM Ecommerce_Data LIMIT 20"))
            state["available_categories"] = [row[0] for row in result.fetchall()]

            result = conn.execute(text("SELECT Product_Name FROM Ecommerce_Data LIMIT 10"))
            state["sample_products"] = [row[0] for row in result.fetchall()]

        logger.info(f"[SCHEMA_INSPECTOR] Found {len(columns)} columns")
        logger.info(f"[SCHEMA_INSPECTOR] Found {len(state['available_categories'])} categories")

    except Exception as e:
        logger.error(f"[SCHEMA_INSPECTOR] Error: {e}")
        state["error_message"] = f"Database schema inspection failed: {e}"

    return state


def generate_query_node(state: RecommendationState) -> RecommendationState:
    """
    Uses LLM to understand intent and generate SQL query
    The LLM has access to conversation history via checkpointer
    """
    logger.info("[QUERY_GENERATOR] Generating SQL query with LLM...")

    if state.get("error_message"):
        return state

    prompt = ChatPromptTemplate.from_messages([
        ("system", QUERY_GENERATOR_PROMPT),
        ("human", "User Query: {user_query}\n\nGenerate the SQL query:")
    ])

    try:
        chain = prompt | gemini_model
        response = chain.invoke({
            "user_query": state["user_query"],
            "columns": ", ".join(state["available_columns"]),
            "categories": ", ".join(state["available_categories"][:10]),
            "sample_products": ", ".join(state["sample_products"][:5])
        })

        sql_query = response.content.strip()

        sql_query = re.sub(r'```sql\s*|\s*```', '', sql_query)
        sql_query = sql_query.strip()

        if not sql_query.endswith(';'):
            sql_query += ';'

        state["sql_query"] = sql_query
        logger.info(f"[QUERY_GENERATOR] Generated query: {sql_query}")

    except Exception as e:
        logger.error(f"[QUERY_GENERATOR] Error: {e}")
        state["error_message"] = f"Query generation failed: {e}"

    return state


def validate_query_node(state: RecommendationState) -> RecommendationState:
    """
    Validates SQL query for safety and syntax
    """
    logger.info("[QUERY_VALIDATOR] Validating SQL query...")

    if state.get("error_message"):
        return state

    sql_query = state["sql_query"]
    errors = []

    dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'TRUNCATE', 'CREATE']
    for keyword in dangerous_keywords:
        if keyword in sql_query.upper():
            errors.append(f"Dangerous keyword '{keyword}' detected")

    if not sql_query.upper().strip().startswith('SELECT'):
        errors.append("Query must be a SELECT statement")

    if 'LIMIT' not in sql_query.upper():
        errors.append("Query must include LIMIT clause")

    if 'FROM' not in sql_query.upper():
        errors.append("Query must include FROM clause")

    state["validation_errors"] = errors

    if errors:
        logger.warning(f"[QUERY_VALIDATOR] ✗ Validation failed: {errors}")
        state["error_message"] = f"Invalid query: {', '.join(errors)}"
    else:
        logger.info("[QUERY_VALIDATOR] Query is valid and safe")

    return state


def execute_query_node(state: RecommendationState) -> RecommendationState:
    """
    Executes the validated SQL query
    """
    logger.info("[QUERY_EXECUTOR] Executing SQL query...")

    if state.get("error_message") or state.get("validation_errors"):
        return state

    try:
        with engine.connect() as conn:
            sql_query = state["sql_query"].rstrip(';')

            result = conn.execute(text(sql_query))
            rows = result.fetchall()
            columns = result.keys()

            results = [dict(zip(columns, row)) for row in rows]
            state["query_results"] = results

            logger.info(f"[QUERY_EXECUTOR] Found {len(results)} results")

    except Exception as e:
        logger.error(f"[QUERY_EXECUTOR] Error: {e}")
        state["error_message"] = f"Query execution failed: {e}"

    return state


def format_response_node(state: RecommendationState) -> RecommendationState:
    """
    Uses LLM to format results into natural language response
    The LLM has access to conversation history via checkpointer
    """
    logger.info("[RESPONSE_FORMATTER] Formatting response...")

    if state.get("error_message"):
        state["formatted_response"] = (
            "I apologize, but I encountered an issue searching for products. "
            "Could you please rephrase your request or try browsing our categories?"
        )
        return state

    prompt = ChatPromptTemplate.from_messages([
        ("system", RESPONSE_FORMATTER_PROMPT),
        ("human", """User Query: {user_query}
            Search Results: {results}
            Format response:""")
    ])

    try:
        chain = prompt | gemini_model
        response = chain.invoke({
            "user_query": state["user_query"],
            "results": state["query_results"][:10],
            "categories": ", ".join(state.get("available_categories", [])[:5])
        })

        state["formatted_response"] = response.content
        logger.info("[RESPONSE_FORMATTER]  Response formatted")

    except Exception as e:
        logger.error(f"[RESPONSE_FORMATTER] Error: {e}")
        results = state["query_results"][:5]
        response = f"Found {len(state['query_results'])} products:\n\n"
        for idx, product in enumerate(results, 1):
            response += f"{idx}. {product.get('Product_Name', 'N/A')}\n"
            if 'Category' in product:
                response += f"   Category: {product['Category']}\n"
            if 'Price' in product:
                response += f"   Price: ${product['Price']}\n"
        state["formatted_response"] = response

    return state
