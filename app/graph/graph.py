from langgraph.graph import StateGraph, END
from app.graph.nodes import AgentState, generate_sql, validate_sql_semantic, validate_and_execute, correct_sql, should_retry

def build_graph():
    g = StateGraph(AgentState)
    g.add_node("generate", generate_sql)
    g.add_node("validate", validate_sql_semantic)
    g.add_node("execute", validate_and_execute)
    g.add_node("correct", correct_sql)

    g.set_entry_point("generate")
    g.add_edge("generate", "validate")
    g.add_edge("validate", "execute")
    g.add_conditional_edges("execute", should_retry, {"correct": "correct", "end": END})
    g.add_edge("correct", "validate")

    return g.compile()
