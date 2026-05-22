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