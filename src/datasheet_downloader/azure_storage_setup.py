"""
Azure Blob Storage setup utilities.

This module provides functions to create and configure Azure Blob Storage
for storing datasheet PDFs.
"""

import os
import sys
import json
import logging
import subprocess
from typing import Dict, Any, Optional, Union

try:
    from azure.storage.blob import BlobServiceClient, ContentSettings
    from azure.core.exceptions import ResourceExistsError
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("azure_setup.log"), logging.StreamHandler()]
)
logger = logging.getLogger("azure_setup")


def check_azure_cli_installed() -> bool:
    """
    Check if Azure CLI is installed.
    
    Returns:
        True if Azure CLI is installed, False otherwise
    """
    try:
        result = subprocess.run(
            ["az", "--version"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def login_to_azure_cli(interactive: bool = True) -> bool:
    """
    Login to Azure CLI.
    
    Args:
        interactive: Whether to use interactive login
        
    Returns:
        True if login successful, False otherwise
    """
    if interactive:
        try:
            result = subprocess.run(
                ["az", "login"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Error logging in to Azure CLI: {e}")
            return False
    else:
        # For non-interactive login, use service principal credentials
        # This requires setting environment variables:
        # AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID
        try:
            client_id = os.environ.get("AZURE_CLIENT_ID")
            client_secret = os.environ.get("AZURE_CLIENT_SECRET")
            tenant_id = os.environ.get("AZURE_TENANT_ID")
            
            if not all([client_id, client_secret, tenant_id]):
                logger.error("Missing service principal credentials in environment variables")
                return False
            
            result = subprocess.run(
                [
                    "az", "login", 
                    "--service-principal",
                    "-u", client_id,
                    "-p", client_secret,
                    "--tenant", tenant_id
                ],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Error logging in to Azure CLI with service principal: {e}")
            return False


def check_resource_group_exists(
    resource_group: str
) -> bool:
    """
    Check if a resource group exists in Azure.
    
    Args:
        resource_group: Name of the resource group
        
    Returns:
        True if resource group exists, False otherwise
    """
    try:
        result = subprocess.run(
            [
                "az", "group", "show",
                "--name", resource_group
            ],
            capture_output=True,
            text=True
        )
        
        return result.returncode == 0
        
    except Exception as e:
        logger.error(f"Error checking resource group: {e}")
        return False


def create_resource_group(
    resource_group: str, 
    location: str = "germanywestcentral"
) -> bool:
    """
    Create a resource group in Azure if it doesn't exist.
    
    Args:
        resource_group: Name of the resource group
        location: Azure region
        
    Returns:
        True if resource group created successfully or already exists, False otherwise
    """
    # First check if resource group already exists
    if check_resource_group_exists(resource_group):
        logger.info(f"Resource group '{resource_group}' already exists")
        return True
        
    # Create the resource group if it doesn't exist
    try:
        result = subprocess.run(
            [
                "az", "group", "create",
                "--name", resource_group,
                "--location", location
            ],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info(f"Resource group '{resource_group}' created successfully")
            return True
        else:
            logger.error(f"Error creating resource group: {result.stderr}")
            return False
    
    except Exception as e:
        logger.error(f"Error creating resource group: {e}")
        return False


def check_storage_account_exists(
    resource_group: str,
    storage_account: str
) -> bool:
    """
    Check if a storage account exists in Azure.
    
    Args:
        resource_group: Name of the resource group
        storage_account: Name of the storage account
        
    Returns:
        True if storage account exists, False otherwise
    """
    try:
        result = subprocess.run(
            [
                "az", "storage", "account", "show",
                "--name", storage_account,
                "--resource-group", resource_group
            ],
            capture_output=True,
            text=True
        )
        
        return result.returncode == 0
        
    except Exception as e:
        logger.error(f"Error checking storage account: {e}")
        return False


def create_storage_account(
    resource_group: str,
    storage_account: str,
    location: str = "germanywestcentral",
    sku: str = "Standard_LRS"
) -> bool:
    """
    Create a storage account in Azure if it doesn't exist.
    
    Args:
        resource_group: Name of the resource group
        storage_account: Name of the storage account
        location: Azure region
        sku: Storage account SKU
        
    Returns:
        True if storage account created successfully or already exists, False otherwise
    """
    # First check if storage account already exists
    if check_storage_account_exists(resource_group, storage_account):
        logger.info(f"Storage account '{storage_account}' already exists")
        return True
        
    # Create the storage account if it doesn't exist
    try:
        result = subprocess.run(
            [
                "az", "storage", "account", "create",
                "--name", storage_account,
                "--resource-group", resource_group,
                "--location", location,
                "--sku", sku,
                "--kind", "StorageV2"
            ],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info(f"Storage account '{storage_account}' created successfully")
            return True
        else:
            logger.error(f"Error creating storage account: {result.stderr}")
            return False
    
    except Exception as e:
        logger.error(f"Error creating storage account: {e}")
        return False


def get_storage_connection_string(
    resource_group: str,
    storage_account: str
) -> Optional[str]:
    """
    Get the connection string for a storage account.
    
    Args:
        resource_group: Name of the resource group
        storage_account: Name of the storage account
        
    Returns:
        Connection string if successful, None otherwise
    """
    try:
        result = subprocess.run(
            [
                "az", "storage", "account", "show-connection-string",
                "--name", storage_account,
                "--resource-group", resource_group,
                "--output", "json"
            ],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            data = json.loads(result.stdout)
            connection_string = data.get("connectionString")
            return connection_string
        else:
            logger.error(f"Error getting connection string: {result.stderr}")
            return None
    
    except Exception as e:
        logger.error(f"Error getting connection string: {e}")
        return None


def check_blob_container_exists(
    resource_group: str,
    storage_account: str,
    container_name: str
) -> bool:
    """
    Check if a blob container exists in a storage account.
    
    Args:
        resource_group: Name of the resource group
        storage_account: Name of the storage account
        container_name: Name of the container
        
    Returns:
        True if container exists, False otherwise
    """
    try:
        result = subprocess.run(
            [
                "az", "storage", "container", "exists",
                "--name", container_name,
                "--account-name", storage_account,
                "--auth-mode", "login"
            ],
            capture_output=True,
            text=True
        )
        
        # Parse the JSON output to get the exists property
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get("exists", False)
        
        return False
        
    except Exception as e:
        logger.error(f"Error checking blob container: {e}")
        return False


def create_blob_container(
    resource_group: str,
    storage_account: str,
    container_name: str
) -> bool:
    """
    Create a blob container in a storage account if it doesn't exist.
    
    Args:
        resource_group: Name of the resource group
        storage_account: Name of the storage account
        container_name: Name of the container
        
    Returns:
        True if container created successfully or already exists, False otherwise
    """
    # First check if container already exists
    if check_blob_container_exists(resource_group, storage_account, container_name):
        logger.info(f"Blob container '{container_name}' already exists")
        return True
        
    # Create the container if it doesn't exist
    try:
        result = subprocess.run(
            [
                "az", "storage", "container", "create",
                "--name", container_name,
                "--account-name", storage_account,
                "--resource-group", resource_group,
                "--auth-mode", "login"
            ],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info(f"Blob container '{container_name}' created successfully")
            return True
        else:
            logger.error(f"Error creating blob container: {result.stderr}")
            return False
    
    except Exception as e:
        logger.error(f"Error creating blob container: {e}")
        return False


def create_container_sdk(
    connection_string: str,
    container_name: str
) -> bool:
    """
    Create a blob container using the Azure SDK.
    
    Args:
        connection_string: Storage account connection string
        container_name: Name of the container
        
    Returns:
        True if container created successfully, False otherwise
    """
    if not AZURE_AVAILABLE:
        logger.error("Azure Storage SDK not available")
        return False
    
    try:
        # Create the BlobServiceClient
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        
        # Create the container
        try:
            blob_service_client.create_container(container_name)
            logger.info(f"Container '{container_name}' created successfully")
            return True
        except ResourceExistsError:
            logger.info(f"Container '{container_name}' already exists")
            return True
        
    except Exception as e:
        logger.error(f"Error creating container: {e}")
        return False


def setup_azure_storage(
    resource_group: str,
    storage_account: str,
    container_name: str = "datasheets",
    location: str = "germanywestcentral",
    use_cli: bool = True
) -> Dict[str, Any]:
    """
    Set up Azure Storage for datasheet uploads.
    
    Args:
        resource_group: Name of the resource group
        storage_account: Name of the storage account
        container_name: Name of the container
        location: Azure region
        use_cli: Whether to use Azure CLI
        
    Returns:
        Dictionary with setup results
    """
    results = {
        "success": False,
        "connection_string": None,
        "container_name": container_name,
        "storage_account": storage_account,
        "resource_group": resource_group
    }
    
    # Check prerequisites
    if use_cli:
        if not check_azure_cli_installed():
            logger.error("Azure CLI is not installed")
            results["error"] = "Azure CLI is not installed"
            return results
        
        # Login to Azure
        if not login_to_azure_cli():
            logger.error("Failed to login to Azure CLI")
            results["error"] = "Failed to login to Azure CLI"
            return results
        
        # Create resource group
        if not create_resource_group(resource_group, location):
            logger.error(f"Failed to create resource group '{resource_group}'")
            results["error"] = f"Failed to create resource group '{resource_group}'"
            return results
        
        # Create storage account
        if not create_storage_account(resource_group, storage_account, location):
            logger.error(f"Failed to create storage account '{storage_account}'")
            results["error"] = f"Failed to create storage account '{storage_account}'"
            return results
        
        # Get connection string
        connection_string = get_storage_connection_string(resource_group, storage_account)
        if not connection_string:
            logger.error("Failed to get connection string")
            results["error"] = "Failed to get connection string"
            return results
        
        results["connection_string"] = connection_string
        
        # Create container
        if not create_blob_container(resource_group, storage_account, container_name):
            logger.error(f"Failed to create blob container '{container_name}'")
            results["error"] = f"Failed to create blob container '{container_name}'"
            return results
    
    else:
        # Use SDK approach if connection string is provided or if CLI approach failed
        if not AZURE_AVAILABLE:
            logger.error("Azure Storage SDK not available")
            results["error"] = "Azure Storage SDK not available"
            return results
        
        # If we have a connection string from CLI or it was provided externally
        connection_string = results.get("connection_string") or os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        
        if not connection_string:
            logger.error("No connection string available")
            results["error"] = "No connection string available"
            return results
        
        # Create container using SDK
        if not create_container_sdk(connection_string, container_name):
            logger.error(f"Failed to create container '{container_name}' using SDK")
            results["error"] = f"Failed to create container '{container_name}' using SDK"
            return results
        
        results["connection_string"] = connection_string
    
    # Success
    results["success"] = True
    logger.info("Azure Storage setup completed successfully")
    return results


def create_folder_structure_in_container(
    connection_string: str,
    container_name: str,
    folder_names: list
) -> bool:
    """
    Create a folder structure in a blob container.
    
    Args:
        connection_string: Storage account connection string
        container_name: Name of the container
        folder_names: List of folder names to create
        
    Returns:
        True if folders created successfully, False otherwise
    """
    if not AZURE_AVAILABLE:
        logger.error("Azure Storage SDK not available")
        return False
    
    try:
        # Create the BlobServiceClient
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        
        # Get container client
        container_client = blob_service_client.get_container_client(container_name)
        
        # Create each folder (by creating an empty blob with folder name ending with '/')
        for folder_name in folder_names:
            # Ensure folder name ends with '/'
            if not folder_name.endswith('/'):
                folder_name += '/'
            
            # Create an empty blob to represent the folder
            blob_client = container_client.get_blob_client(folder_name)
            blob_client.upload_blob(data="", overwrite=True)
            logger.info(f"Created folder: {folder_name}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error creating folder structure: {e}")
        return False


def main():
    """Main entry point for the script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Set up Azure Storage for datasheet uploads")
    parser.add_argument("--resource-group", required=True, help="Name of the resource group")
    parser.add_argument("--storage-account", required=True, help="Name of the storage account")
    parser.add_argument("--container", default="datasheets", help="Name of the blob container")
    parser.add_argument("--location", default="germanywestcentral", help="Azure region")
    parser.add_argument("--no-cli", action="store_false", dest="use_cli", 
                      help="Don't use Azure CLI, use SDK only")
    parser.add_argument("--create-folder", action="append", dest="folders",
                      help="Create folder in container (can be used multiple times)")
    
    args = parser.parse_args()
    
    # Set up Azure Storage
    results = setup_azure_storage(
        resource_group=args.resource_group,
        storage_account=args.storage_account,
        container_name=args.container,
        location=args.location,
        use_cli=args.use_cli
    )
    
    if not results["success"]:
        print(f"Error: {results.get('error', 'Unknown error')}")
        return 1
    
    print(f"Azure Storage set up successfully")
    print(f"Connection string: {results['connection_string']}")
    
    # Create folder structure if specified
    if args.folders:
        if create_folder_structure_in_container(
            connection_string=results["connection_string"],
            container_name=args.container,
            folder_names=args.folders
        ):
            print(f"Created folders: {', '.join(args.folders)}")
        else:
            print("Failed to create folders")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
