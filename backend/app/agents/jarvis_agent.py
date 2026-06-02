"""
JARVIS Orchestrator Agent — LangGraph-based multi-agent pipeline.

Graph topology:
  user_message → intent_classifier → router →
    ├── reddit_agent   ┐
    ├── research_agent │
    ├── security_agent ├── tool_executor → synthesizer → response
    ├── strategy_agent │
    ├── memory_agent   ┘
    └── chat_agent (direct)
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

import structlog
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from app.agents.state import AgentMessage, JarvisState
from app.agents.tools import ALL_TOOLS, TOOL_NAMES
from app.core.config import settings

logger = structlog.get_logger(__name__)

MAX_ITERATIONS = 5


def _llm(temperature: float = 0.3) -> ChatAnthropic:
    return ChatAnthropic(
        model=settings.ANTHROPIC_MODEL,
        api_key=settings.ANTHROPIC_API_KEY,
        temperature=temperature,
        max_tokens=settings.AI_MAX_TOKENS,
    )


def _llm_with_tools() -> ChatAnthropic:
    return _llm().bind_tools(ALL_TOOLS)


# ─── Node: Intent Classifier ──────────────────────────────────────

INTENT_SYSTEM = """You are JARVIS intent classifier. Analyze the user message and return JSON.

Intents:
- reddit: analyzing subreddits, finding trends, Reddit topics, community research
- research: general research, web search, finding information, competitive analysis
- security: investigating accounts, detecting manipulation, OSINT, suspicious behavior
- strategy: decision making, growth planning, option evaluation, business strategy
- memory: storing/retrieving information from memory, past conversations
- report: generating reports from existing analysis
- chat: general conversation, questions about JARVIS, other

Return ONLY valid JSON: {"intent": "...", "confidence": 0.95, "entities": {...}}"""


async def classify_intent(state: JarvisState) -> JarvisState:
    """Classify user intent to route to the right agent."""
    messages = state.get("messages", [])
    last_user = next(
        (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
    )

    llm = _llm(temperature=0)
    response = await llm.ainvoke([
        SystemMessage(content=INTENT_SYSTEM),
        HumanMessage(content=last_user),
    ])

    try:
        raw = response.content
        if "```" in raw:
            raw = raw.split("```")[1].lstrip("json").strip()
        data = json.loads(raw)
        intent = data.get("intent", "chat")
        confidence = float(data.get("confidence", 0.5))
    except Exception:
        intent = "chat"
        confidence = 0.5

    logger.info("agent.intent", intent=intent, confidence=confidence)
    return {**state, "intent": intent, "confidence": confidence, "iterations": 0}


# ─── Node: Memory Retrieval ───────────────────────────────────────

async def retrieve_memories(state: JarvisState) -> JarvisState:
    """Pull relevant memories before agent execution."""
    messages = state.get("messages", [])
    last_user = next(
        (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
    )
    user_id = state.get("user_id", "")
    memories: List[str] = []

    if user_id and last_user:
        try:
            from app.core.database import AsyncSessionLocal
            from app.services.memory_service import MemoryService

            async with AsyncSessionLocal() as db:
                svc = MemoryService(db)
                memories = await svc.get_context_memories(
                    uuid.UUID(user_id), last_user, limit=5
                )
        except Exception as exc:
            logger.warning("agent.memory_retrieval_failed", error=str(exc))

    return {**state, "memories": memories}


# ─── Node: Reddit Agent ───────────────────────────────────────────

REDDIT_SYSTEM = """You are JARVIS Reddit Intelligence Agent.
You specialize in analyzing Reddit communities, discovering trends, and finding growth opportunities.

Available tools: analyze_subreddit_tool, search_reddit_tool, store_memory_tool

When analyzing a subreddit:
1. Use analyze_subreddit_tool to get full analysis
2. Identify top trends and content gaps
3. Store key insights in memory with store_memory_tool
4. Provide actionable recommendations

Be specific. Cite data. Challenge assumptions."""


async def reddit_agent(state: JarvisState) -> JarvisState:
    messages = state.get("messages", [])
    memories = state.get("memories", [])
    last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

    memory_ctx = "\n".join(f"- {m}" for m in memories) if memories else "No relevant memories."
    system = REDDIT_SYSTEM + f"\n\nRelevant memories:\n{memory_ctx}"

    llm = _llm_with_tools()
    response = await llm.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=last_user),
    ])

    new_messages = list(messages) + [{"role": "assistant", "content": str(response.content), "name": "reddit_agent", "tool_call_id": None}]
    return {
        **state,
        "messages": new_messages,
        "agent_result": {"agent": "reddit", "response": response.content},
        "tools_called": state.get("tools_called", []) + ["reddit_agent"],
    }


# ─── Node: Research Agent ─────────────────────────────────────────

RESEARCH_SYSTEM = """You are JARVIS Research Intelligence Agent.
You conduct deep, multi-source research and synthesize findings into actionable intelligence.

Available tools: research_topic_tool, search_reddit_tool, store_memory_tool

Research principles:
1. Separate facts from assumptions — explicitly label both
2. Rate confidence for each claim
3. Identify what you DON'T know (knowledge gaps)
4. Cite sources
5. Challenge the user's framing if it contains assumptions"""


async def research_agent(state: JarvisState) -> JarvisState:
    messages = state.get("messages", [])
    memories = state.get("memories", [])
    last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

    memory_ctx = "\n".join(f"- {m}" for m in memories) if memories else "No relevant memories."
    system = RESEARCH_SYSTEM + f"\n\nRelevant memories:\n{memory_ctx}"

    llm = _llm_with_tools()
    response = await llm.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=last_user),
    ])

    new_messages = list(messages) + [{"role": "assistant", "content": str(response.content), "name": "research_agent", "tool_call_id": None}]
    return {
        **state,
        "messages": new_messages,
        "agent_result": {"agent": "research", "response": response.content},
        "tools_called": state.get("tools_called", []) + ["research_agent"],
    }


# ─── Node: Security Agent ─────────────────────────────────────────

SECURITY_SYSTEM = """You are JARVIS Security Intelligence Agent.
You investigate Reddit accounts and communities for suspicious behavior patterns.

Available tools: investigate_account_tool, search_reddit_tool, store_memory_tool

Investigation principles:
1. Be factual — never make unsupported claims
2. For every finding: state the evidence, confidence level, and alternative explanations
3. Identify vote manipulation, brigading, sockpuppets, coordinated behavior
4. Recommend specific monitoring actions
5. Escalation criteria: when the evidence warrants alerting others"""


async def security_agent(state: JarvisState) -> JarvisState:
    messages = state.get("messages", [])
    memories = state.get("memories", [])
    last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

    memory_ctx = "\n".join(f"- {m}" for m in memories) if memories else "No relevant memories."
    system = SECURITY_SYSTEM + f"\n\nRelevant memories:\n{memory_ctx}"

    llm = _llm_with_tools()
    response = await llm.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=last_user),
    ])

    new_messages = list(messages) + [{"role": "assistant", "content": str(response.content), "name": "security_agent", "tool_call_id": None}]
    return {
        **state,
        "messages": new_messages,
        "agent_result": {"agent": "security", "response": response.content},
        "tools_called": state.get("tools_called", []) + ["security_agent"],
    }


# ─── Node: Strategy Agent ─────────────────────────────────────────

STRATEGY_SYSTEM = """You are JARVIS Strategy Intelligence Agent.
You help make better decisions by analyzing options critically.

Available tools: analyze_strategy_tool, search_memory_tool, store_memory_tool

Decision framework:
For each option provide:
  Pros | Cons | Risks | Effort | Impact | Timeline

Then provide:
  Recommendation + reasoning
  Conditions that change the recommendation
  First 3 concrete steps
  Assumptions you're challenging

Do NOT just agree with the user. Identify flaws in their plan."""


async def strategy_agent(state: JarvisState) -> JarvisState:
    messages = state.get("messages", [])
    memories = state.get("memories", [])
    last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

    memory_ctx = "\n".join(f"- {m}" for m in memories) if memories else "No relevant memories."
    system = STRATEGY_SYSTEM + f"\n\nPast decisions and context:\n{memory_ctx}"

    llm = _llm(temperature=0.5)
    response = await llm.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=last_user),
    ])

    new_messages = list(messages) + [{"role": "assistant", "content": str(response.content), "name": "strategy_agent", "tool_call_id": None}]
    return {
        **state,
        "messages": new_messages,
        "agent_result": {"agent": "strategy", "response": response.content},
        "tools_called": state.get("tools_called", []) + ["strategy_agent"],
    }


# ─── Node: Memory Agent ───────────────────────────────────────────

async def memory_agent(state: JarvisState) -> JarvisState:
    messages = state.get("messages", [])
    memories = state.get("memories", [])
    last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

    memory_ctx = "\n".join(f"- {m}" for m in memories) if memories else "No memories found."

    system = f"""You are JARVIS Memory Agent.
You manage the user's long-term knowledge base.

Available tools: search_memory_tool, store_memory_tool

Current retrieved memories:
{memory_ctx}

Help the user store, find, or organize their knowledge."""

    llm = _llm_with_tools()
    response = await llm.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=last_user),
    ])

    new_messages = list(messages) + [{"role": "assistant", "content": str(response.content), "name": "memory_agent", "tool_call_id": None}]
    return {
        **state,
        "messages": new_messages,
        "agent_result": {"agent": "memory", "response": response.content},
        "tools_called": state.get("tools_called", []) + ["memory_agent"],
    }


# ─── Node: Chat Agent ─────────────────────────────────────────────

CHAT_SYSTEM = """You are JARVIS, a personal AI intelligence operating system.

You are NOT a generic chatbot. You are a professional intelligence tool for Reddit operators.

Your capabilities:
- Reddit community analysis and intelligence
- Multi-source research and synthesis
- Security investigations and threat detection
- Strategic planning and decision analysis
- Long-term memory and knowledge management

When users ask what you can do, be specific about each capability.
When users make vague requests, ask one clarifying question to get specific."""


async def chat_agent(state: JarvisState) -> JarvisState:
    messages = state.get("messages", [])
    memories = state.get("memories", [])
    last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

    memory_ctx = "\n".join(f"- {m}" for m in memories) if memories else ""
    system = CHAT_SYSTEM
    if memory_ctx:
        system += f"\n\nRelevant context from memory:\n{memory_ctx}"

    llm = _llm(temperature=0.7)
    response = await llm.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=last_user),
    ])

    new_messages = list(messages) + [{"role": "assistant", "content": str(response.content), "name": "chat_agent", "tool_call_id": None}]
    return {
        **state,
        "messages": new_messages,
        "agent_result": {"agent": "chat", "response": response.content},
        "tools_called": state.get("tools_called", []) + ["chat_agent"],
    }


# ─── Node: Auto-save memory ───────────────────────────────────────

async def auto_save_memory(state: JarvisState) -> JarvisState:
    """Automatically save important AI responses to memory."""
    result = state.get("agent_result", {})
    user_id = state.get("user_id", "")
    intent = state.get("intent", "chat")

    if not user_id or intent == "chat":
        return state

    response_text = str(result.get("response", ""))[:2000]
    if len(response_text) < 100:
        return state

    try:
        from app.core.database import AsyncSessionLocal
        from app.services.memory_service import MemoryService
        from app.models.memory import MemoryType

        messages = state.get("messages", [])
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

        type_map = {
            "reddit": MemoryType.SUBREDDIT_REPORT,
            "research": MemoryType.RESEARCH,
            "security": MemoryType.NOTE,
            "strategy": MemoryType.DECISION,
        }
        mem_type = type_map.get(intent, MemoryType.INSIGHT)

        async with AsyncSessionLocal() as db:
            svc = MemoryService(db)
            await svc.auto_store(
                user_id=uuid.UUID(user_id),
                title=f"{intent.title()} — {last_user[:60]}",
                content=response_text,
                memory_type=mem_type,
                source_type="agent",
                importance=0.6,
            )
    except Exception as exc:
        logger.warning("agent.auto_save_failed", error=str(exc))

    return state


# ─── Routing Logic ────────────────────────────────────────────────

def route_by_intent(state: JarvisState) -> str:
    intent = state.get("intent", "chat")
    routes = {
        "reddit": "reddit_agent",
        "research": "research_agent",
        "security": "security_agent",
        "strategy": "strategy_agent",
        "memory": "memory_agent",
        "report": "chat_agent",  # Report generation handled via REST
        "chat": "chat_agent",
    }
    return routes.get(intent, "chat_agent")


# ─── Build Graph ──────────────────────────────────────────────────

def build_jarvis_graph():
    """Construct and compile the JARVIS LangGraph agent graph."""
    graph = StateGraph(JarvisState)

    # Add nodes
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("retrieve_memories", retrieve_memories)
    graph.add_node("reddit_agent", reddit_agent)
    graph.add_node("research_agent", research_agent)
    graph.add_node("security_agent", security_agent)
    graph.add_node("strategy_agent", strategy_agent)
    graph.add_node("memory_agent", memory_agent)
    graph.add_node("chat_agent", chat_agent)
    graph.add_node("auto_save_memory", auto_save_memory)

    # Edges
    graph.add_edge(START, "classify_intent")
    graph.add_edge("classify_intent", "retrieve_memories")
    graph.add_conditional_edges("retrieve_memories", route_by_intent, {
        "reddit_agent": "reddit_agent",
        "research_agent": "research_agent",
        "security_agent": "security_agent",
        "strategy_agent": "strategy_agent",
        "memory_agent": "memory_agent",
        "chat_agent": "chat_agent",
    })
    for agent_node in ["reddit_agent", "research_agent", "security_agent",
                       "strategy_agent", "memory_agent", "chat_agent"]:
        graph.add_edge(agent_node, "auto_save_memory")
    graph.add_edge("auto_save_memory", END)

    return graph.compile()


# Compiled graph — singleton
_graph = None

def get_graph():
    global _graph
    if _graph is None:
        _graph = build_jarvis_graph()
    return _graph
