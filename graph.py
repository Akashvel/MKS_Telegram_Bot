# graph.py
from dotenv import load_dotenv
load_dotenv()
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from postgres_tool import query_postgres
from rag_tool import search_privacy_policy
from typing import TypedDict, Annotated
import operator

# --- State ---
class AgentState(TypedDict):
    messages: Annotated[list, operator.add]

def _build_system_prompt(is_admin: bool) -> str:
    tools_desc = (
        """1. query_postgres: Query the PostgreSQL database (sms_dev). Always write SELECT queries only.
    2. search_privacy_policy: Search company policy documents (PDF-based RAG). Use for checklists, policies, procedures, privacy, or compliance."""
        if is_admin else
        """1. search_privacy_policy: Search company policy documents (PDF-based RAG). Use for checklists, policies, procedures, privacy, or compliance."""        
    )
    structured_output = """Make the response table structured if needed. Format it accordinly"""
    db_rules = """
    DATABASE RULES (always follow when using query_postgres):

    SCHEMA MODEL:
    - 'candidates' (also may be called 'profile') is the BASE table — it is the master record
      for every person (holds name, email, and other identity fields).
    - Every other table uses user_id as a FOREIGN KEY referencing candidates.user_id.
    - NEVER return raw user_id numbers — always resolve to a readable name/email via candidates.

    QUERY STRATEGY (follow this order every time):
    1. If unsure which table holds the data, discover tables first:
         SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';
    2. Inspect a specific table's columns:
         SELECT column_name FROM information_schema.columns
         WHERE table_name = '<table>' AND table_schema = 'public';
    3. Always anchor your query on candidates and JOIN the data table on user_id:
         SELECT c.name, c.email, t.<columns>
         FROM candidates c
         JOIN <data_table> t ON t.user_id = c.user_id
         WHERE <condition>;

    EXAMPLE PATTERNS:
    -- "Who has skill X?"
        SELECT c.name, c.email, s.*
        FROM candidates c
        JOIN <skills_table> s ON s.user_id = c.user_id
        WHERE s.<skill_column> ILIKE '%X%';

    -- "Show profile + extra data for person Y"
        SELECT c.name, c.email, t.*
        FROM candidates c
        JOIN <any_table> t ON t.user_id = c.user_id
        WHERE c.name ILIKE '%Y%';

    -- "Count people with property X"
        SELECT COUNT(DISTINCT c.user_id)
        FROM candidates c
        JOIN <table> t ON t.user_id = c.user_id
        WHERE t.<column> = 'X';
    """ if is_admin else ""

    return f"""You are a helpful assistant. Available tools:\n    {tools_desc}\n    {db_rules}Choose the right tool based on the question."""

def _should_continue(state: AgentState):
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END

def build_app(is_admin: bool = True):
    """Build a compiled LangGraph app scoped to the given role."""
    available_tools = [query_postgres, search_privacy_policy] if is_admin else [search_privacy_policy]
    _llm = ChatGroq(model="qwen/qwen3-32b", temperature=0).bind_tools(available_tools)
    system_prompt = _build_system_prompt(is_admin)

    def agent_node(state: AgentState):
        system = SystemMessage(content=system_prompt)
        response = _llm.invoke([system] + state["messages"])
        return {"messages": [response]}

    g = StateGraph(AgentState)
    g.add_node("agent", agent_node)
    g.add_node("tools", ToolNode(available_tools))
    g.set_entry_point("agent")
    g.add_conditional_edges("agent", _should_continue, {"tools": "tools", END: END})
    g.add_edge("tools", "agent")
    return g.compile()

# Default admin app used by main.py
app = build_app(is_admin=True)