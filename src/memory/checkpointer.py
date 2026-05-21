import os
from langgraph.checkpoint.sqlite import SqliteSaver
from pathlib import Path
import sqlite3

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
        os.getenv("SQLITE_PATH", os.path.join("..","data","memory.db"))
    )
    #print(f"PATH : {db_path}")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"PATH : {db_path}")
    # Use proper SQLite connection string format
    #conn_string = f"sqlite:///{db_path.resolve()}"
    #checkpointer = SqliteSaver.from_conn_string(conn_string)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    
    # Create SqliteSaver
    persistent_memory = SqliteSaver(conn)
    print(f"checkpointer : {persistent_memory}")
    return persistent_memory


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