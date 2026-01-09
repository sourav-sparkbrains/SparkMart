import logging
import traceback
from langchain.agents import create_agent
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain.tools import tool

from common.llm import groq_model
from core.prompts.prompts import GENERAL_QUERY_PROMPT, COMPLAINT_HANDLER_PROMPT,PURCHASE_AGENT_PROMPT
from db.database import db
from core.agents.tools import save_order_tool
from common.shared_config import checkpointer, store

from core.workflow.recommendation_graph import recommendation_graph

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

toolkit = SQLDatabaseToolkit(db=db, llm=groq_model)
complaint_tools = toolkit.get_tools() + [save_order_tool]

general_query_agent = create_agent(
    groq_model,
    tools=[],
    checkpointer=checkpointer,
    store=store,
    system_prompt=GENERAL_QUERY_PROMPT
)

complain_handler_agent = create_agent(
    groq_model,
    tools=complaint_tools,
    checkpointer=checkpointer,
    store=store,
    system_prompt=COMPLAINT_HANDLER_PROMPT
)

purchase_agent = create_agent(
    groq_model,
    tools=[save_order_tool],
    checkpointer=checkpointer,
    store=store,
    system_prompt=PURCHASE_AGENT_PROMPT
)


@tool("general_query_tool", return_direct=True)
def general_query_tool(request: str, session_id: str) -> str:
    """
    Handle general customer queries such as greetings, store info,
    policies, and non-specific questions.
    Input:
        Natural language message from the user.
        Example: "Hi, what services do you provide?"
    """
    logger.info(f"[GENERAL_QUERY] Session: {session_id} | Request: {request[:100]}")

    try:
        result = general_query_agent.invoke(
            {"messages": [{"role": "user", "content": request}]},
            {"configurable": {"thread_id": session_id}}
        )
        response = result["messages"][-1].content
        logger.info(f"[GENERAL_QUERY] Response generated successfully")
        return response

    except Exception as e:
        logger.error(f"[GENERAL_QUERY] Error: {str(e)}")
        logger.error(traceback.format_exc())
        return "I apologize, but I encountered an error. How else can I help you?"


@tool("recommendation_tool", return_direct=True)
def recommendation_tool(request: str, session_id: str) -> str:
    """
    Handle product recommendations, searches, filtering, and guiding users
    to select/purchase items.
    Input:
        User request related to exploring categories, finding products,
        comparing items, or expressing intent to buy.
    """
    logger.info("=" * 80)
    logger.info(f"[RECOMMENDATION_GRAPH] Session: {session_id}")
    logger.info(f"[RECOMMENDATION_GRAPH] Request: {request}")
    logger.info("=" * 80)

    try:
        initial_state = {
            "user_query": request,
            "session_id": session_id,
            "available_columns": [],
            "available_categories": [],
            "sample_products": [],
            "intent": "",
            "keywords": [],
            "sql_query": "",
            "validation_errors": [],
            "query_results": [],
            "formatted_response": "",
            "error_message": ""
        }

        logger.info("[RECOMMENDATION_GRAPH] Invoking graph workflow with memory...")

        config = {"configurable": {"thread_id": session_id}}
        final_state = recommendation_graph.invoke(initial_state, config)

        response_text = final_state.get("formatted_response", "")

        if not response_text:
            response_text = (
                "I apologize, but I couldn't complete your request. "
                "Please try rephrasing or let me know how I can help!"
            )

        logger.info("=" * 80)
        logger.info("[RECOMMENDATION_GRAPH] SUCCESS")
        logger.info(f"[RECOMMENDATION_GRAPH] SQL: {final_state.get('sql_query', 'N/A')}")
        logger.info(f"[RECOMMENDATION_GRAPH] Results: {len(final_state.get('query_results', []))}")
        logger.info("=" * 80)

        return response_text

    except Exception as e:
        logger.error("=" * 80)
        logger.error("[RECOMMENDATION_GRAPH] ERROR")
        logger.error(f"[RECOMMENDATION_GRAPH] Error: {str(e)}")
        logger.error(f"[RECOMMENDATION_GRAPH] Traceback:\n{traceback.format_exc()}")
        logger.error("=" * 80)

        return (
            "I apologize for the technical issue. Let me help you differently.\n\n"
            "Could you please tell me:\n"
            "1. What type of product are you looking for?\n"
            "2. Any specific brand or price range?\n\n"
            "I'll do my best to find what you need!"
        )


@tool("purchase_agent_tool", return_direct=True)
def purchase_agent_tool(request: str, session_id: str) -> str:
    """
    Handle purchase requests and order placement.
    This agent:
    1. Extracts product name from conversation history (previous recommendation results)
    2. Confirms which product the user wants to buy
    3. Calls save_order_tool to place the order
    4. Returns order confirmation
    Input:
        User expressions of purchase intent like:
        - "I want to buy it"
        - "Add to cart"
        - "I'll take the first one"
        - "Purchase [product name]"
    """
    logger.info("=" * 80)
    logger.info(f"[PURCHASE_AGENT] Session: {session_id}")
    logger.info(f"[PURCHASE_AGENT] Request: {request}")
    logger.info("=" * 80)

    try:
        enhanced_request = f"{request}\n\nSession ID: {session_id}"

        result = purchase_agent.invoke(
            {"messages": [{"role": "user", "content": enhanced_request}]},
            {"configurable": {"thread_id": session_id}}
        )

        response = result["messages"][-1].content

        logger.info("=" * 80)
        logger.info("[PURCHASE_AGENT] SUCCESS")
        logger.info(f"[PURCHASE_AGENT] Response: {response[:200]}...")
        logger.info("=" * 80)

        return response

    except Exception as e:
        logger.error("=" * 80)
        logger.error("[PURCHASE_AGENT] ERROR")
        logger.error(f"[PURCHASE_AGENT] Error: {str(e)}")
        logger.error(f"[PURCHASE_AGENT] Traceback:\n{traceback.format_exc()}")
        logger.error("=" * 80)

        return (
            "I apologize, but I'm having trouble processing your purchase request.\n\n"
            "Could you please specify which product you'd like to purchase? "
            "You can say something like 'I want to buy the [product name]' or "
            "'Add [product name] to cart'."
        )



@tool("complain_handler_tool", return_direct=True)
def complain_handler_tool(request: str, session_id: str) -> str:
    """
    Handle customer complaints, refund requests, damaged product issues,
    or any order-related concerns.
    The agent:
    - Asks for order_id if missing
    - Looks up the order in the database using SQL tools
    - Guides user to describe the issue
    - Extracts file URLs from [FILE_ATTACHED: url] format
    - Saves complaint with save_order_tool
    Input:
        Natural language complaint message, may include [FILE_ATTACHED: url]
    """
    logger.info("=" * 80)
    logger.info(f"[COMPLAINT] Session: {session_id}")
    logger.info(f"[COMPLAINT] Request: {request}")

    if "[FILE_ATTACHED:" in request:
        logger.info("[COMPLAINT] File attachment detected")

    logger.info("=" * 80)

    try:
        result = complain_handler_agent.invoke(
            {"messages": [{"role": "user", "content": request}]},
            {"configurable": {"thread_id": session_id}}
        )

        response = result["messages"][-1].content

        logger.info("=" * 80)
        logger.info("[COMPLAINT] SUCCESS")
        logger.info(f"[COMPLAINT] Response: {response[:200]}...")
        logger.info("=" * 80)

        return response

    except Exception as e:
        logger.error("=" * 80)
        logger.error("[COMPLAINT] ERROR")
        logger.error(f"[COMPLAINT] Error: {str(e)}")
        logger.error(f"[COMPLAINT] Traceback:\n{traceback.format_exc()}")
        logger.error("=" * 80)

        return (
            "I sincerely apologize for the inconvenience. I'm having trouble processing your complaint right now.\n\n"
            "Please provide:\n"
            "1. Your Order ID (format: order_xxxxx)\n"
            "2. Description of the issue\n\n"
            "I'll make sure your concern is addressed immediately."
        )
