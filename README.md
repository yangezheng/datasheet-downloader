# Datasheet Downloader

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Poetry](https://img.shields.io/badge/packaging-poetry-cyan.svg)](https://python-poetry.org/)

A powerful tool for automatically searching and downloading electronic component datasheets using Manufacturer Part Numbers (MPNs).

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
