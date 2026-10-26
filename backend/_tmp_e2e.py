import os, uuid, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from documents.services import embed_and_store, delete_document_from_chromadb
from documents.ai_services import _get_document_text_from_chromadb
from chat.services import retrieve_chunks

doc_id = str(uuid.uuid4())
chunks = ["Photosynthesis converts light energy into chemical energy in plants.",
          "The mitochondria is the powerhouse of the cell."]
try:
    embed_and_store(doc_id, chunks, "e2e.txt", "2026-10-26")
    print("text:", _get_document_text_from_chromadb(doc_id)[:50])
    found, _, _, _ = retrieve_chunks("What does photosynthesis do?", document_id=doc_id, top_k=1)
    print("retrieved:", found)
finally:
    delete_document_from_chromadb(doc_id)
