"""Document storage and Tier 1/Tier 2 index management."""

import json
import logging

logger = logging.getLogger(__name__)


def upload_document(s3_client, tenant_id, folder_id, document_id, filename, content):
    """Upload a document to S3."""
    key = f"tenants/{tenant_id}/folders/{folder_id}/docs/{document_id}"
    s3_client.upload(key, content, content_type="application/octet-stream")
    return key


def get_document_content(s3_client, storage_url):
    """Download document content from S3."""
    return s3_client.download(storage_url).decode("utf-8", errors="replace")


def build_folder_index(s3_client, tenant_id, folder_id, documents):
    """Build a Tier 2 index.json for a folder and upload to S3."""
    index = []
    for doc in documents:
        index.append({
            "id": str(doc["id"]),
            "filename": doc["filename"],
            "summary": doc.get("summary", ""),
            "metadata": doc.get("metadata", {}),
        })

    key = f"tenants/{tenant_id}/folders/{folder_id}/index.json"
    s3_client.upload(key, json.dumps(index))
    return key
