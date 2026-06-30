from contextlib import asynccontextmanager
import asyncio

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from rag import RagSession
from graph import build_app

# Pre-built graphs stored at startup
_apps: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    print("Loading embedding model and RAG database...")
    await asyncio.to_thread(lambda: RagSession().initialize())
    print("RAG ready.")

    print("Building agent graphs...")
    _apps["admin"] = await asyncio.to_thread(build_app, True)
    _apps["guest"] = await asyncio.to_thread(build_app, False)
    print("Application ready.")

    yield

    # --- Shutdown ---
    _apps.clear()


app = FastAPI(title="MKS Assistant API", version="1.0.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    role: str = "guest"  # "admin" or "guest"


class ChatResponse(BaseModel):
    reply: str
    role: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "graphs_loaded": list(_apps.keys())}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    role = req.role.lower()
    if role not in ("admin", "guest"):
        raise HTTPException(status_code=400, detail="role must be 'admin' or 'guest'")

    from langchain_core.messages import HumanMessage

    graph = _apps.get(role)
    if graph is None:
        raise HTTPException(status_code=503, detail="Application not ready yet")

    result = await asyncio.to_thread(
        graph.invoke,
        {"messages": [HumanMessage(content=req.message)]},
    )

    return ChatResponse(reply=result["messages"][-1].content, role=role)
