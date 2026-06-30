from rag import *


session = RagSession()
session.initialize()

print("RAG Chat ready. Type 'exit' to quit.\n")

while True:
    question = input("You: ").strip()
    if question.lower() == "exit":
        break
    
    results = session.query(question)
    
    if not results:
        print("Bot: No relevant documents found.\n")
        continue
    
    for doc in results:
        print(f"\n[Score: {doc['similarity_score']:.3f} | Page {doc['metadata'].get('page')}]")
        print(doc['content'])
    print()