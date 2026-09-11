#!/usr/bin/env python
"""
Migration script to move old per-document ChromaDB collections to shared collection.
Run this after upgrading to multi-document support.

Usage:
    python migrate_to_shared_collection.py
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from documents.models import Document
from django.conf import settings
from config.chroma import get_chroma_client

CHROMA_PATH = os.path.join(settings.BASE_DIR, "chroma_db")


def migrate_documents():
    """Migrate all documents from old per-doc collections to shared collection."""
    client = get_chroma_client()
    
    # Get or create shared collection
    shared_collection = client.get_or_create_collection(name="all_documents")
    
    # Get all existing collections
    collections = client.list_collections()
    print(f"Found {len(collections)} collections")
    
    migrated_count = 0
    skipped_count = 0
    
    for collection_obj in collections:
        collection_name = collection_obj.name
        
        # Skip if already the shared collection
        if collection_name == "all_documents":
            continue
        
        # Extract document ID from collection name (format: doc_{uuid})
        if not collection_name.startswith("doc_"):
            print(f"Skipping non-document collection: {collection_name}")
            skipped_count += 1
            continue
        
        document_id = collection_name[4:]  # Remove 'doc_' prefix
        
        # Verify document exists in database
        try:
            doc = Document.objects.get(id=document_id)
        except Document.DoesNotExist:
            print(f"Document {document_id} not found in database, skipping")
            skipped_count += 1
            continue
        
        print(f"Migrating document: {doc.filename} ({document_id})")
        
        try:
            # Get old collection
            old_collection = client.get_collection(name=collection_name)
            
            # Get all data from old collection
            data = old_collection.get()
            
            if not data['ids']:
                print(f"  No data in collection, skipping")
                skipped_count += 1
                continue
            
            # Prepare data for shared collection
            new_ids = [f"{document_id}_chunk_{i}" for i in range(len(data['ids']))]
            
            # Update metadata to include doc_id and upload_date
            updated_metadatas = []
            for i, old_meta in enumerate(data['metadatas']):
                new_meta = {
                    'source': old_meta.get('source', doc.filename),
                    'doc_id': document_id,
                    'upload_date': doc.created_at.isoformat(),
                    'chunk_index': old_meta.get('chunk_index', i)
                }
                updated_metadatas.append(new_meta)
            
            # Add to shared collection
            shared_collection.upsert(
                ids=new_ids,
                documents=data['documents'],
                embeddings=data['embeddings'],
                metadatas=updated_metadatas
            )
            
            print(f"  Migrated {len(data['ids'])} chunks")
            migrated_count += 1
            
            # Optional: Delete old collection
            # client.delete_collection(name=collection_name)
            # print(f"  Deleted old collection")
            
        except Exception as e:
            print(f"  Error migrating {collection_name}: {e}")
            continue
    
    print(f"\nMigration complete:")
    print(f"  Migrated: {migrated_count} documents")
    print(f"  Skipped: {skipped_count} collections")
    print(f"\nOld collections have been preserved.")
    print(f"To delete them manually, run:")
    print(f"  python manage.py shell")
    print(f"  >>> import chromadb")
    print(f"  >>> client = chromadb.PersistentClient(path='chroma_db')")
    print(f"  >>> client.delete_collection('doc_<uuid>')")


if __name__ == "__main__":
    print("=" * 60)
    print("ChromaDB Migration: Per-Document → Shared Collection")
    print("=" * 60)
    print()
    
    confirm = input("This will migrate all documents to shared collection. Continue? (y/n): ")
    if confirm.lower() != 'y':
        print("Migration cancelled")
        sys.exit(0)
    
    migrate_documents()
