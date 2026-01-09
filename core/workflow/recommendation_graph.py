import logging
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from core.workflow.schema import RecommendationState
from core.workflow.nodes import (
    intent_detector_node,
    inspect_schema_node,
    generate_query_node,
    validate_query_node,
    execute_query_node,
    format_response_node)

logger = logging.getLogger(__name__)

graph_checkpointer = MemorySaver()

def build_recommendation_graph():
    """
    Builds the LangGraph workflow for product recommendations
    Memory is managed by the checkpointer automatically
    """
    workflow = StateGraph(RecommendationState)

    workflow.add_node("intent_detector", intent_detector_node)
    workflow.add_node("schema_inspector", inspect_schema_node)
    workflow.add_node("query_generator", generate_query_node)
    workflow.add_node("query_validator", validate_query_node)
    workflow.add_node("query_executor", execute_query_node)
    workflow.add_node("response_formatter", format_response_node)

    workflow.set_entry_point("schema_inspector")
    workflow.add_edge("schema_inspector", "query_generator")
    workflow.add_edge("query_generator", "query_validator")
    workflow.add_edge("query_validator", "query_executor")
    workflow.add_edge("query_executor", "response_formatter")
    workflow.add_edge("response_formatter", END)

    return workflow.compile(checkpointer=graph_checkpointer)


recommendation_graph = build_recommendation_graph()

logger.info(" Recommendation graph compiled successfully with short-term memory")