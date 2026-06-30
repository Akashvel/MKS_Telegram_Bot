from rag import *


#-------------Step by step Invoke-------------#
# Process all PDFs in the data directory
all_pdf_documents = process_all_pdfs("pdfs_to_embed")
# Split and Chunk all those read pdf's
chunks=split_documents(all_pdf_documents)
## initialize the embedding manager
embedding_manager=EmbeddingManager()
generated_embedding = embedding_manager.generate_embeddings([doc.page_content for doc in chunks])
## Store it in Chroma DB
vectorstore=VectorStore()
vectorstore.add_documents(chunks,generated_embedding)
# vectorstore=VectorStore()
# embedding_manager=EmbeddingManager()
# print(vectorstore.collection.count())  # should be exactly 40, not 80
