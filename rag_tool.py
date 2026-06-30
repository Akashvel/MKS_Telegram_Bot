from langchain_core.tools import tool
from rag import RagSession

session = RagSession()  # singleton; initialize() called by FastAPI lifespan

@tool("search_privacy_policy")
def search_privacy_policy(query: str) -> str:
    """
    Search the company's privacy policy documents to answer questions about
    data handling, privacy rights, retention, third-party sharing, employee
    privacy, GDPR/compliance clauses, etc. Use this for ANY question about
    company policy. Available to both Admin and Guest users.
    """
    docs = session.query(query)
    #store = _get_store()
    #docs = store.similarity_search(query, k=4)
    if not docs:
        return "No relevant information found in the privacy policy documents."

    parts = []
    for doc in docs:
        parts.append(f"Source: {doc['metadata'].get('source_file')} | Page: {doc['metadata'].get('page')} | Content:{doc['content']}")
    return "\n\n".join(parts)
