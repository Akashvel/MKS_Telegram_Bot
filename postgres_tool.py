# tools/postgres_tool.py
import psycopg2
import os
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv()

# psycopg2 uses postgresql:// not postgresql+psycopg://
DB_URL = os.getenv("POSTGRES_URL", "").replace("postgresql+psycopg://", "postgresql://")

@tool
def query_postgres(sql: str) -> str:
    """
    Run a SELECT query against the PostgreSQL database.
    Use this to look up employee/candidate records, counts, skills, or any structured data.
    Only SELECT statements are allowed.
    """
    if not sql.strip().upper().startswith("SELECT"):
        return "Error: Only SELECT queries are allowed."
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        col_names = [desc[0] for desc in cur.description]
        cur.close()
        conn.close()
        if not rows:
            return "No results found."
        result = [dict(zip(col_names, row)) for row in rows]
        return "\n".join(str(r) for r in result)
    except Exception as e:
        return f"Database error: {str(e)}"