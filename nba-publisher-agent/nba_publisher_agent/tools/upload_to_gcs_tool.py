import os
from typing import Dict
from google.cloud import storage
from google.adk.tools.tool_context import ToolContext


def upload_to_gcs(local_file_path: str, tool_context: ToolContext, bucket_name: str = "nba_daily_summary_podcast_audios") -> Dict[str, str]:
    """
    Uploads an audio file to Google Cloud Storage and makes it publicly accessible.
    
    Authentication is handled via GOOGLE_APPLICATION_CREDENTIALS environment variable
    pointing to a service account JSON key file.

    Args:
        local_file_path: Path to the local audio file to upload.
        tool_context: The ADK tool context.
        bucket_name: Name of the GCS bucket (default: "nba_daily_summary_podcast_audios").

    Returns:
        Dictionary with status and file information including public URL.
    """
    try:
        # Check if GOOGLE_APPLICATION_CREDENTIALS is set
        credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not credentials_path:
            return {
                "status": "error",
                "message": "GOOGLE_APPLICATION_CREDENTIALS environment variable not set. Please set it to the path of your service account JSON key file.",
                "file_path": local_file_path
            }
        
        # Verify the credentials file exists
        if not os.path.exists(credentials_path):
            return {
                "status": "error",
                "message": f"Service account credentials file not found at: {credentials_path}",
                "file_path": local_file_path
            }
        
        # Initialize GCS client (will automatically use GOOGLE_APPLICATION_CREDENTIALS)
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        
        # Extract filename from path for destination blob name
        filename = os.path.basename(local_file_path)
        destination_blob_name = filename
        
        # Upload file
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(local_file_path)
        
        # Make the file public
        blob.make_public()
        
        return {
            "status": "success",
            "message": f"Successfully uploaded {filename} to GCS bucket '{bucket_name}'",
            "file_path": local_file_path,
            "destination_blob_name": destination_blob_name,
            "bucket_name": bucket_name,
            "public_url": blob.public_url,
            "file_size": blob.size
        }
        
    except Exception as e:
        error_msg = str(e)[:200]
        return {
            "status": "error", 
            "message": f"GCS upload failed: {error_msg}",
            "file_path": local_file_path
        }
