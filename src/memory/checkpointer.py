import os
from langgraph.checkpoint.sqlite import SqliteSaver
from pathlib import Path


def get_checkpointer():
    """
    Dev:  SqliteSaver — file-based, zero setup
    Prod: PostgresSaver — shared across ECS tasks
    """
    env = os.getenv("ENVIRONMENT", "development")

    if env == "production":
        try:
            from langgraph.checkpoint.postgres import (
                PostgresSaver
            )
            return PostgresSaver.from_conn_string(
                os.getenv("DATABASE_URL",
                           "postgresql://localhost/copilot")
            )
        except Exception as e:
            print(f"Postgres unavailable, using SQLite: {e}")

    # Default: SQLite
    db_path = Path(
        os.getenv("SQLITE_PATH", "./data/memory.db")
    )
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return SqliteSaver.from_conn_string(str(db_path))


# # Every graph invocation needs config with thread_id
# from graph.graph import copilot_graph
# from graph.state import initial_state


# def run_query(
#     query:     str,
#     thread_id: str,   # conversation ID
#     user_id:   str = "user",
#     time_range:str = "last_month",
# ) -> dict:
#     config = {
#         "configurable": {
#             "thread_id": thread_id
#         }
#     }

#     state  = initial_state(query, thread_id, user_id,
#                             time_range)
#     result = copilot_graph.invoke(state, config=config)
#     return result

# # In Streamlit — thread_id from session_state:
# import streamlit as st

# if "thread_id" not in st.session_state:
#     import uuid
#     st.session_state.thread_id = str(uuid.uuid4())

# result = run_query(
#     query     = user_query,
#     thread_id = st.session_state.thread_id,
#     user_id   = "streamlit-user",
# )