"""
Simple Azure integration for datasheet PDFs.
This script uploads datasheets to Azure Storage and stores paths in PostgreSQL.
"""

import os
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
import psycopg2
from psycopg2.extras import execute_batch
from dotenv import load_dotenv

# Import Azure Storage module
try:
    from azure.storage.blob import BlobServiceClient, ContentSettings
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("azure_datasheet_upload.log"), logging.StreamHandler()]
)
logger = logging.getLogger("azure_datasheet_upload")


class SimpleDatasheetUploader:
    """Upload datasheets to Azure Storage and store paths in PostgreSQL."""
    
    def __init__(
        self, 
        storage_connection_string: str,
        pg_host: str,
        pg_database: str,
        pg_user: str,
        pg_password: str,
        pg_port: int = 5432,
        blob_container: str = "datasheets",
    ):
        """
        Initialize the datasheet uploader.
        
        Args:
            storage_connection_string: Azure Blob Storage connection string
            pg_host: PostgreSQL server hostname
            pg_database: PostgreSQL database name
            pg_user: PostgreSQL user
            pg_password: PostgreSQL password
            pg_port: PostgreSQL port (default: 5432)
            blob_container: Blob container name for PDF files
        """
        self.storage_connection_string = storage_connection_string
        self.blob_container = blob_container
        
        self.pg_params = {
            "host": pg_host,
            "database": pg_database,
            "user": pg_user,
            "password": pg_password,
            "port": pg_port,
            "sslmode": "require"
        }
        
        # Initialize Azure and PostgreSQL clients
        self.blob_service_client = None
        self.pg_conn = None
        
    
    def initialize_azure_storage(self) -> bool:
        """
        Initialize Azure Blob Storage connection.
        
        Returns:
            True if initialization successful, False otherwise
        """
        if not AZURE_AVAILABLE:
            logger.error("Azure Storage SDK not available. Install with: pip install azure-storage-blob")
            return False
        
        try:
            # Create the BlobServiceClient
            self.blob_service_client = BlobServiceClient.from_connection_string(self.storage_connection_string)
            
            # Create container if it doesn't exist
            try:
                self.blob_service_client.create_container(self.blob_container)
                logger.info(f"Container created: {self.blob_container}")
            except Exception:
                logger.info(f"Container already exists: {self.blob_container}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error initializing Azure Blob Storage: {e}")
            return False
    
    def initialize_postgres(self) -> bool:
        """
        Initialize PostgreSQL connection.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            self.pg_conn = psycopg2.connect(**self.pg_params)
            logger.info("Connected to PostgreSQL database")
            return True
        
        except Exception as e:
            logger.error(f"Error connecting to PostgreSQL database: {e}")
            return False


    def upload_datasheet(self, pdf_path: str) -> Dict[str, Any]:
        """
        Upload a single datasheet to Azure Blob Storage and store path in PostgreSQL.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dictionary with result information
        """
        file_name = os.path.basename(pdf_path)
        mpn = os.path.splitext(file_name)[0]  # Use filename without extension as MPN
        table_name = "integrated_circuits_ics__power_management_ics__voltage_regulato"

        def ensure_column_exists(cursor, table, column):
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = %s AND column_name = %s
            """, (table, column))
            if not cursor.fetchone():
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT;")

        try:
            folder_name = "voltage_regulator_linear"
            blob_name = f"{folder_name}/{file_name}"

            # Upload to Azure Blob Storage
            blob_client = self.blob_service_client.get_blob_client(
                container=self.blob_container, 
                blob=blob_name
            )
            with open(pdf_path, "rb") as data:
                blob_client.upload_blob(
                    data,
                    overwrite=True,
                    content_settings=ContentSettings(content_type="application/pdf")
                )

            azure_blob_url = blob_client.url

            # Store path in PostgreSQL
            cursor = self.pg_conn.cursor()

            # Ensure required columns exist
            ensure_column_exists(cursor, table_name, "file_path")
            ensure_column_exists(cursor, table_name, "azure_blob_url")
            self.pg_conn.commit()

            # Perform UPSERT
            cursor.execute(f"""
                INSERT INTO {table_name} (mpn, file_path, azure_blob_url) 
                VALUES (%s, %s, %s)
                ON CONFLICT (mpn) DO UPDATE SET 
                    file_path = EXCLUDED.file_path,
                    azure_blob_url = EXCLUDED.azure_blob_url
            """, (mpn, blob_name, azure_blob_url))

            self.pg_conn.commit()

            logger.info(f"Uploaded {file_name} to Azure and stored path in database")
            return {
                "success": True,
                "mpn": mpn,
                "blob_url": azure_blob_url
            }

        except Exception as e:
            self.pg_conn.rollback()
            logger.error(f"Error uploading {file_name}: {e}")
            return {"success": False, "error": str(e), "file": file_name}

        finally:
            if 'cursor' in locals():
                cursor.close()

    
    def upload_datasheets_folder(self, folder_path: str) -> Dict[str, Any]:
        """
        Upload all PDF files in a folder to Azure and store paths in PostgreSQL.
        
        Args:
            folder_path: Path to folder containing datasheet PDFs
            
        Returns:
            Dictionary with upload results
        """
        # Initialize connections
        if not self.blob_service_client:
            if not self.initialize_azure_storage():
                return {"success": False, "error": "Failed to initialize Azure Storage"}
        
        if not self.pg_conn:
            if not self.initialize_postgres():
                return {"success": False, "error": "Failed to initialize PostgreSQL"}
        
        # Find all PDF files
        folder = Path(folder_path)
        pdf_files = list(folder.glob("*.pdf"))
        
        results = {
            "success": True,
            "total": len(pdf_files),
            "uploaded": 0,
            "failed": 0,
            "errors": []
        }
        
        # Process each file
        for pdf_file in pdf_files:
            result = self.upload_datasheet(str(pdf_file))
            
            if result["success"]:
                results["uploaded"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(result)
        
        # Close PostgreSQL connection
        if self.pg_conn:
            self.pg_conn.close()
            self.pg_conn = None
        
        results["success"] = results["failed"] == 0
        
        logger.info(f"Upload complete: {results['uploaded']} succeeded, {results['failed']} failed")
        return results


def main():
    """Main entry point for the script."""
    # Load environment variables from .env file
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="Upload datasheets to Azure Storage and store paths in PostgreSQL")
    
    # Required arguments
    parser.add_argument("datasheets_dir", help="Directory containing datasheet PDFs")
    parser.add_argument("--connection-string", help="Azure Blob Storage connection string")
    parser.add_argument("--pg-host", help="PostgreSQL server hostname")
    parser.add_argument("--pg-database", help="PostgreSQL database name")
    parser.add_argument("--pg-user", help="PostgreSQL user")
    parser.add_argument("--pg-password", help="PostgreSQL password")
    
    # Optional arguments
    parser.add_argument("--pg-port", type=int, help="PostgreSQL port")
    parser.add_argument("--container", help="Azure Blob container name")
    parser.add_argument("--env-file", default=".env", help="Path to .env file")
    parser.add_argument("--no-organize", action="store_false", dest="organize", 
                      help="Don't organize datasheets by manufacturer")
    
    args = parser.parse_args()
    
    # Load from specified .env file if provided
    if args.env_file and args.env_file != ".env":
        load_dotenv(args.env_file)
    
    # Get connection string from args or environment
    connection_string = args.connection_string or os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        print("Error: Azure Storage connection string not provided. Use --connection-string or set AZURE_STORAGE_CONNECTION_STRING in .env file")
        return 1
    
    # Get PostgreSQL connection params from args or environment
    pg_host = args.pg_host or os.environ.get("PG_HOST")
    pg_database = args.pg_database or os.environ.get("PG_DATABASE")
    pg_user = args.pg_user or os.environ.get("PG_USER")
    pg_password = args.pg_password or os.environ.get("PG_PASSWORD")
    pg_port = args.pg_port or int(os.environ.get("PG_PORT", "5432"))
    
    # Check required PostgreSQL params
    if not all([pg_host, pg_database, pg_user, pg_password]):
        print("Error: PostgreSQL connection details not provided. Use command line arguments or set in .env file")
        return 1
    
    # Get container name
    blob_container = args.container or os.environ.get("BLOB_CONTAINER", "datasheets")
    
    # Create uploader and process files
    uploader = SimpleDatasheetUploader(
        storage_connection_string=connection_string,
        pg_host=pg_host,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
        pg_port=pg_port,
        blob_container=blob_container,
    )
    
    result = uploader.upload_datasheets_folder(args.datasheets_dir)
    
    if result["success"]:
        print(f"Successfully uploaded {result['uploaded']} of {result['total']} datasheets")
        return 0
    else:
        print(f"Completed with errors: {result['uploaded']} succeeded, {result['failed']} failed")
        return 1


if __name__ == "__main__":
    exit(main())
