"""
Command-line interface for datasheet-downloader
"""

import argparse
import os
import sys
from typing import List, Optional
import logging

from .downloader import DatasheetDownloader, download_datasheet

logger = logging.getLogger('datasheet_downloader')


def parse_args(args: Optional[List[str]] = None):
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Download datasheets for electronic components by MPN"
    )
    
    # Main input options - either MPN or CSV file
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "mpn",
        nargs="?",
        help="Manufacturer Part Number(s) to search for",
    )
    
    input_group.add_argument(
        "-f", "--file",
        help="File containing list of MPNs (one per line)",
    )
    
    input_group.add_argument(
        "--csv",
        help="Process a CSV file with columns for part numbers and datasheet URLs",
    )
    
    # Output options
    parser.add_argument(
        "-o", "--output-dir",
        default=os.getcwd(),
        help="Directory to save downloaded datasheets (default: current directory)",
    )
    
    # Browser options
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run browser in visible mode (not headless)",
    )
    
    # Search options
    parser.add_argument(
        "--direct-sources",
        action="store_true",
        help="Skip Google search and only use direct manufacturer/distributor sources",
    )
    
    parser.add_argument(
        "--delay",
        type=float,
        default=3.0,
        help="Delay between requests in seconds (default: 3.0)",
    )
    
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="List available datasheets but don't download them",
    )
    
    # Debug options
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode with even more verbose logging",
    )
    
    return parser.parse_args(args)


def main(args: Optional[List[str]] = None):
    """Main entry point for the CLI"""
    parsed_args = parse_args(args)
    
    # Configure logging
    if parsed_args.debug:
        log_level = logging.DEBUG
    elif parsed_args.verbose:
        log_level = logging.INFO
    else:
        log_level = logging.WARNING
        
    logging.basicConfig(
        level=log_level, 
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.FileHandler("datasheet_download.log"), logging.StreamHandler()]
    )
    
    # Create output directory if it doesn't exist
    os.makedirs(parsed_args.output_dir, exist_ok=True)
    
    if parsed_args.no_headless:
        logger.info("Running in visible mode")
    
    # Initialize the downloader
    downloader = DatasheetDownloader(
        headless=not parsed_args.no_headless,
        download_dir=parsed_args.output_dir,
        delay_seconds=parsed_args.delay
    )
    
    # Process CSV file mode
    if parsed_args.csv:
        logger.info(f"Processing CSV file: {parsed_args.csv}")
        downloader.process_csv_file(parsed_args.csv)
        return 0
    
    # Get MPNs from arguments or file
    mpns = []
    if parsed_args.mpn:
        mpns.append(parsed_args.mpn)
    
    if parsed_args.file:
        try:
            with open(parsed_args.file, 'r') as f:
                file_mpns = [line.strip() for line in f if line.strip()]
                mpns.extend(file_mpns)
        except Exception as e:
            logger.error(f"Error reading MPN file: {e}")
            return 1
    
    # Batch processing or single MPN mode
    try:
        with downloader:
            for mpn in mpns:
                try:
                    if parsed_args.direct_sources:
                        # Use only direct sources
                        results = downloader.search_direct_sources(mpn)
                        
                        if parsed_args.list_only:
                            print(f"\nDatasheets found from direct sources for {mpn}:")
                            if not results:
                                print("  No datasheets found")
                            else:
                                for i, result in enumerate(results, 1):
                                    print(f"{i}. {result['title']}")
                                    print(f"   Source: {result['source']}")
                                    print(f"   URL: {result['url']}")
                                    print()
                        elif results:
                            # Download the first result
                            success, message, filepath, download_url = downloader.download_direct_pdf(results[0]['url'], mpn)
                            if success:
                                print(f"Downloaded datasheet for {mpn} to {filepath}")
                            else:
                                print(f"Failed to download datasheet: {message}")
                        else:
                            print(f"No datasheet found for {mpn} from direct sources")
                            
                    else:
                        # Use search workflow
                        if parsed_args.list_only:
                            # Just list available datasheets
                            results = downloader.get_datasheet(mpn, download=False)
                            print(f"\nDatasheets found for {mpn}:")
                            if not results:
                                print("  No datasheets found")
                            else:
                                for i, result in enumerate(results, 1):
                                    print(f"{i}. {result['title']}")
                                    print(f"   Source: {result['source']}")
                                    print(f"   URL: {result['url']}")
                                    print()
                        else:
                            # Download the datasheet
                            success, message, filepath, download_url = downloader.search_by_part_number(mpn)
                            if success:
                                print(f"Downloaded datasheet for {mpn} to {filepath}")
                            else:
                                print(f"No datasheet found for {mpn}: {message}")
                except Exception as e:
                    logger.error(f"Error processing {mpn}: {e}")
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 