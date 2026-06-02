"""Shared state types for the JARVIS LangGraph agent graph."""
from __future__ import annotations

import uuid
from typing import Any, Annotated, Dict, List, Optional, TypedDict

from langgraph.graph import add_messages


class AgentMessage(TypedDict):
    role: str  # "user" | "assistant" | "system" | "tool"
    content: str
    name: Optional[str]
    tool_call_id: Optional[str]


class JarvisState(TypedDict):
    """Shared state passed through the JARVIS agent graph."""
    # Core
    user_id: str
    conversation_id: str
    messages: Annotated[List[AgentMessage], add_messages]

    # Intent routing
    intent: Optional[str]          # detected intent: reddit|research|security|strategy|memory|report|chat
    confidence: float

    # Context
    memories: List[str]            # retrieved memory snippets
    context: Dict[str, Any]        # caller-provided extra context

    # Results
    agent_result: Optional[Dict[str, Any]]
    tools_called: List[str]
    error: Optional[str]

    # Routing
    next_agent: Optional[str]
    iterations: int
