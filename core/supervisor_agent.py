from langchain.agents import create_agent

from common.llm import groq_model
from core.prompts.prompts import SUPERVISOR_AGENT_PROMPT
from core.agents.agents import (
    general_query_tool,
    recommendation_tool,
    purchase_agent_tool,
    complain_handler_tool,
)

supervisor_agent = create_agent(
    groq_model,
    tools=[
        general_query_tool,
        recommendation_tool,
        purchase_agent_tool,
        complain_handler_tool,
    ],
    system_prompt=SUPERVISOR_AGENT_PROMPT,
)
