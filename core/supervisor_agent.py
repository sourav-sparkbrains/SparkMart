from langchain.agents import create_agent

from common.llm import groq_model, gemini_model
from core.prompts.prompts import SUPERVISOR_AGENT_PROMPT
from core.agents.agents import (
    general_query_tool,
    recommendation_tool,
    purchase_agent_tool,
    complain_handler_tool,
)

from common.shared_config import checkpointer, store

supervisor_agent = create_agent(
    gemini_model,
    tools=[
        general_query_tool,
        recommendation_tool,
        purchase_agent_tool,
        complain_handler_tool,
    ],
    checkpointer=checkpointer,
    store=store,
    system_prompt=SUPERVISOR_AGENT_PROMPT,
)
