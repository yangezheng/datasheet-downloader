# Datasheet Downloader

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Poetry](https://img.shields.io/badge/packaging-poetry-cyan.svg)](https://python-poetry.org/)

A powerful tool for automatically searching and downloading electronic component datasheets using Manufacturer Part Numbers (MPNs) and uploading them to Azure Blob Storage with PostgreSQL database integration.

## Features

- 📝 **Simple Input** - Provide a single MPN, a text file with multiple MPNs, or a CSV file
- 🔍 **Multi-Source Search** - Searches Google and direct manufacturer/distributor sites
- 🧠 **Intelligent Priority** - Prioritizes official manufacturer datasheets over third-party sources
- ✅ **Datasheet Validation** - Validates PDF files to ensure they are actual datasheets
- 🤖 **Browser Automation** - Uses Playwright for reliable web automation
- 🔄 **Batch Processing** - Process hundreds of components efficiently
- 📊 **Detailed Logging** - Keeps track of all operations and errors

## Installation

### Prerequisites

- Python 3.8+
- [Poetry](https://python-poetry.org/docs/#installation) for dependency management

### Install with Poetry

```bash
# Clone the repository
git clone https://github.com/yourusername/datasheet-downloader.git
cd datasheet-downloader

# Install dependencies
poetry install

# Install browser drivers
poetry run playwright install chromium
```

## Quick Start

### Download a single datasheet

```bash
poetry run datasheet-downloader LM358
```

### Download datasheets for multiple MPNs from a text file

```bash
poetry run datasheet-downloader -f data/mpns.txt -o ./datasheets/
```

### Process a CSV file with part numbers and URLs

```bash
poetry run datasheet-downloader --csv components.csv
```

## Usage Examples

### Command Line Options

```
usage: datasheet-downloader [-h] [-f FILE | --csv CSV] [-o OUTPUT_DIR] [--no-headless]
                           [--direct-sources] [--list-only] [-v] [--debug]
                           [mpn]

Download datasheets for electronic components by MPN

positional arguments:
  mpn                   Manufacturer Part Number(s) to search for

optional arguments:
  -h, --help            show this help message and exit
  -f FILE, --file FILE  File containing list of MPNs (one per line)
  --csv CSV             Process a CSV file with columns for part numbers and datasheet URLs
  -o OUTPUT_DIR, --output-dir OUTPUT_DIR
                        Directory to save downloaded datasheets (default: current directory)
  --no-headless         Run browser in visible mode (not headless)
  --direct-sources      Skip Google search and only use direct manufacturer/distributor sources
  --list-only           List available datasheets but don't download them
  -v, --verbose         Enable verbose output
  --debug               Enable debug mode with even more verbose logging
```

### Working with a Text File of MPNs

Create a text file with one part number per line:

```
# data/mpns.txt
LM358
NCV8715SQ12T2G
ATmega328P
```

Then run:

```bash
poetry run datasheet-downloader -f data/mpns.txt -o ./datasheets/
```

## Azure Storage Integration

The Datasheet Downloader includes functionality to upload datasheets to Azure Blob Storage and store their paths in an Azure PostgreSQL database.

### Prerequisites

- Azure account with an active subscription
- Azure Storage account and container
- Azure PostgreSQL database
- Required Python packages: azure-storage-blob, psycopg2-binary, python-dotenv

### Setup Azure Storage

First, create a `.env` file in the project root:

```
# Azure Storage configuration
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=youraccount;AccountKey=yourkey;EndpointSuffix=core.windows.net

# PostgreSQL database configuration
PG_HOST=your-server.postgres.database.azure.com
PG_DATABASE=your_database_name
PG_USER=your_username
PG_PASSWORD=your_password
PG_PORT=5432

# Azure Blob Storage container
BLOB_CONTAINER=datasheets
```

### Create Azure Resources

Use the Azure Storage setup script to create necessary Azure resources:

```bash
poetry run python -m datasheet_downloader.azure_storage_setup \
  --resource-group "datasheet-resources" \
  --storage-account "datasheetstore" \
  --create-folder "voltage_regulator_linear"
```

This script:
- Creates a resource group (if it doesn't exist)
- Creates a storage account (if it doesn't exist)
- Creates a blob container (if it doesn't exist)
- Creates the "voltage_regulator_linear" folder structure
- Outputs the connection string for future use

### Upload Datasheets to Azure

After downloading datasheets, upload them to Azure and store their paths in PostgreSQL:

```bash
poetry run python -m datasheet_downloader.simple_azure_uploader \
  /Users/yzheng/Projects/datasheet-downloader/datasheets
```

When using environment variables (recommended), simply run:

```bash
poetry run python -m datasheet_downloader.simple_azure_uploader ./datasheets
```

### Upload Options

```
usage: simple_azure_uploader [-h] [--connection-string CONNECTION_STRING]
                            [--pg-host PG_HOST] [--pg-database PG_DATABASE]
                            [--pg-user PG_USER] [--pg-password PG_PASSWORD]
                            [--pg-port PG_PORT] [--container CONTAINER]
                            [--env-file ENV_FILE] [--no-organize]
                            datasheets_dir

Upload datasheets to Azure Storage and store paths in PostgreSQL

positional arguments:
  datasheets_dir        Directory containing datasheet PDFs

options:
  -h, --help            show this help message and exit
  --connection-string CONNECTION_STRING
                        Azure Blob Storage connection string
  --pg-host PG_HOST     PostgreSQL server hostname
  --pg-database PG_DATABASE
                        PostgreSQL database name
  --pg-user PG_USER     PostgreSQL user
  --pg-password PG_PASSWORD
                        PostgreSQL password
  --pg-port PG_PORT     PostgreSQL port
  --container CONTAINER
                        Azure Blob container name
  --env-file ENV_FILE   Path to .env file (default: .env)
```

### Working with a CSV File

The tool can process a CSV file with part numbers and optional datasheet URLs:

```csv
Part Number,Datasheet URL,MIME Type
LM358,https://www.ti.com/lit/ds/symlink/lm358.pdf,application/pdf
NCV8715SQ12T2G,,
```

Then run:

```bash
poetry run datasheet-downloader --csv path/to/components.csv
```

The tool will:
1. Use direct URLs when provided
2. Search for missing URLs
3. Update the CSV with download results

### List Available Datasheets Without Downloading

```bash
poetry run datasheet-downloader LM358 --list-only
```

### Use Only Manufacturer/Distributor Sites (Skip Google)

```bash
poetry run datasheet-downloader -f mpns.txt --direct-sources
```

## How It Works

Datasheet Downloader uses a sophisticated multi-layered approach:

1. **Search Strategy**:
   - First attempts a Google search with the query format `{part_number} datasheet filetype:pdf`
   - Falls back to manufacturer-specific searches if needed
   - Can search direct manufacturer/distributor sites as a last resort

2. **PDF Validation**:
   - Checks file size (50KB - 20MB)
   - Analyzes page count (3-200 pages)
   - Scans content for datasheet terminology
   - Filters out user manuals and catalogs

3. **Source Prioritization**:
   - Prioritizes PDFs from manufacturer domains
   - Follows with trusted distributor domains
   - Uses other sources as a last resort

## Supported Manufacturers

The tool has enhanced support for these manufacturers:

- Texas Instruments (TI)
- ON Semiconductor
- Analog Devices
- NXP Semiconductors
- STMicroelectronics
- Infineon Technologies
- Microchip Technology
- ROHM Semiconductor
- And many more!

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This tool is intended for educational and research purposes only. Always respect copyright and terms of service of websites you access. The authors are not responsible for any misuse of this tool or any violation of terms of service of any website.
