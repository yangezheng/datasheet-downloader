"""
Main module for datasheet downloader functionality
"""

import os
import re
import time
import random
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Union, Tuple
import logging
import urllib.parse
import datetime
from functools import wraps

import requests
from bs4 import BeautifulSoup
import pandas as pd
from playwright.sync_api import sync_playwright, Page, Browser
from tqdm import tqdm
try:
    import fitz  # PyMuPDF for PDF validation
except ImportError:
    fitz = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("datasheet_download.log"), logging.StreamHandler()],
)
logger = logging.getLogger('datasheet_downloader')


class DatasheetDownloader:
    """
    A class to search for and download electronic component datasheets using Playwright.
    """
    
    def __init__(self, headless: bool = True, download_dir: Optional[str] = None, delay_seconds: float = 3.0, retry_count: int = 3):
        """
        Initialize the DatasheetDownloader.
        
        Args:
            headless: Whether to run the browser in headless mode
            download_dir: Directory to save downloaded datasheets (default is current directory)
            delay_seconds: Delay between requests in seconds
            retry_count: Number of download retry attempts
        """
        self.headless = headless
        self.download_dir = download_dir or os.getcwd()
        self.delay_seconds = delay_seconds
        self.retry_count = retry_count
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        
        # Create output directory if it doesn't exist
        os.makedirs(self.download_dir, exist_ok=True)
        logger.info(f"Datasheets will be saved to: {os.path.abspath(self.download_dir)}")
        
        # Manufacturer search URLs
        self.manufacturer_urls = {
            "onsemi": "https://www.onsemi.com/products/",
            "ti": "https://www.ti.com/lit/ds/symlink/",
            "analog": "https://www.analog.com/en/products/",
            "nxp": "https://www.nxp.com/products/",
            "microchip": "https://www.microchip.com/en-us/products/",
            "st": "https://www.st.com/en/",
            "infineon": "https://www.infineon.com/cms/en/product/",
            "vishay": "https://www.vishay.com/en/",
            "rohm": "https://www.rohm.com/products/",
            "toshiba": "https://toshiba.semicon-storage.com/ap-en/semiconductor/product/",
            "diodes": "https://www.diodes.com/products/",
        }
    
    def __enter__(self):
        self.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
    
    def _with_retry(self, func):
        """Decorator for functions that should be retried on failure."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(self.retry_count):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"Attempt {attempt+1}/{self.retry_count} failed: {str(e)}")
                    if attempt == self.retry_count - 1:
                        raise
                    # Exponential backoff
                    delay = (2**attempt) + random.uniform(0, 1)
                    time.sleep(delay)
                    # Reinitialize browser if needed
                    if not self.page or not self.browser:
                        self.stop()
                        self.start()
        return wrapper
        
    def start(self):
        """Start the browser session"""
        self.playwright = sync_playwright().start()
        
        # Enhanced browser launch with better anti-detection settings
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                '--disable-features=IsolateOrigins,site-per-process',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--window-size=1920,1080'
            ]
        )
        
        # Enhanced page context
        self.context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            device_scale_factor=1,
            java_script_enabled=True,
            has_touch=False
        )
        
        # Add extra headers to look more like a real browser
        self.context.set_extra_http_headers({
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        })
        
        # Execute CDP commands to hide automation
        page = self.context.new_page()
        page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        """)
        self.page = page
        
        # Emulate human-like behavior
        self.page.set_default_timeout(30000)  # Longer timeout (30s)
        
        return self
    
    def stop(self):
        """Close the browser session and release resources"""
        if self.page:
            self.page.close()
            self.page = None
        if self.context:
            self.context.close()
            self.context = None
        if self.browser:
            self.browser.close()
            self.browser = None
        if self.playwright:
            self.playwright.stop()
            self.playwright = None
    
    def download_direct_pdf(self, url: str, part_number: str) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """
        Download PDF directly from URL.
        
        Args:
            url: URL of the PDF file
            part_number: Part number for naming the file
            
        Returns:
            Tuple of (success, message, filepath, download_url)
        """
        # Sanitize filename
        part_number = "".join(c if c.isalnum() or c in "-_." else "_" for c in part_number)

        # Check if part number already has a .pdf extension, otherwise add it
        if not part_number.lower().endswith(".pdf"):
            filename = f"{part_number}.pdf"
        else:
            filename = part_number

        # Create full path for the output file
        output_path = os.path.join(self.download_dir, filename)

        # Check if file already exists
        if os.path.exists(output_path):
            return True, f"File already exists: {filename}", output_path, url

        # Custom headers to mimic browser
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        # Try to download with retries
        for attempt in range(self.retry_count):
            try:
                # Stream the download to handle large files efficiently
                with requests.get(url, headers=headers, stream=True, timeout=30) as response:
                    response.raise_for_status()

                    # Check if the response is actually a PDF
                    content_type = response.headers.get("Content-Type", "").lower()
                    if "pdf" not in content_type and "application/octet-stream" not in content_type:
                        return False, f"Not a PDF file (content type: {content_type})", None, None

                    # Get file size for progress bar
                    file_size = int(response.headers.get("content-length", 0))
                    
                    # Save the file with progress bar
                    with open(output_path, "wb") as f, tqdm(
                        desc=os.path.basename(output_path),
                        total=file_size,
                        unit="B",
                        unit_scale=True,
                        unit_divisor=1024,
                    ) as progress:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                            progress.update(len(chunk))

                    logger.info(f"Successfully downloaded: {filename}")
                    return True, f"Successfully downloaded: {filename}", output_path, url

            except requests.exceptions.RequestException as e:
                if attempt < self.retry_count - 1:
                    # Wait with exponential backoff before retrying
                    delay = (2**attempt) + random.uniform(0, 1)
                    time.sleep(delay)
                else:
                    return False, f"Failed to download after {self.retry_count} attempts: {str(e)}", None, None

        return False, "Failed to download with unknown error", None, None
    
    def _identify_manufacturer(self, part_number: str) -> Optional[str]:
        """
        Identify manufacturer from part number prefix.
        
        Args:
            part_number: Component part number
            
        Returns:
            Manufacturer key or None
        """
        part_prefix = part_number.lower()[:3]

        # Common manufacturer prefixes
        prefix_map = {
            "lm": "ti",
            "tps": "ti",
            "ads": "ti",
            "msp": "ti",
            "cc": "ti",
            "tlv": "ti",
            "mc": "nxp",
            "ad": "analog",
            "lt": "analog",
            "max": "analog",
            "ncp": "onsemi",
            "ncv": "onsemi",
            "stm": "st",
            "l6": "st",
            "l7": "st",
            "bsp": "infineon",
            "irfp": "infineon",
            "irf": "infineon",
            "tls": "infineon",
            "tle": "infineon",
            "mic": "microchip",
            "pic": "microchip",
            "atmega": "microchip",
            "bd": "rohm",
        }

        # Check for matches
        for prefix, manufacturer in prefix_map.items():
            if part_prefix.startswith(prefix):
                return manufacturer

        return None
    
    def _normalize_ti_part(self, part_number: str) -> str:
        """
        Normalize a TI part number to the base part for datasheet lookup.
        
        Args:
            part_number: Raw part number like TPS62811QWRWYRQ1
            
        Returns:
            Normalized part number for datasheet lookup like tps62810-q1
        """
        # Convert to lowercase
        part = part_number.lower()

        # Extract the base part number (first alphanumeric segment)
        base_match = re.match(r"([a-z]+\d+)", part)
        if not base_match:
            return part

        base_part = base_match.group(1)

        # Check if it's an automotive/Q1 part
        if "q" in part or "automotive" in part:
            base_part = f"{base_part}-q1"

        return base_part
    
    def _get_manufacturer_specific_search(self, part_number: str) -> Optional[str]:
        """
        Create a manufacturer-specific search query if possible.
        
        Args:
            part_number: Component part number
            
        Returns:
            Search query string or None
        """
        manufacturer = self._identify_manufacturer(part_number)
        if not manufacturer:
            return None
            
        # Map manufacturer key to full name for better search
        manufacturer_names = {
            "ti": "Texas Instruments",
            "nxp": "NXP Semiconductors",
            "analog": "Analog Devices",
            "onsemi": "ON Semiconductor",
            "st": "STMicroelectronics",
            "infineon": "Infineon Technologies",
            "microchip": "Microchip Technology",
            "rohm": "ROHM Semiconductor"
        }
        
        mfr_name = manufacturer_names.get(manufacturer, manufacturer)
        return f"{part_number} {mfr_name} datasheet filetype:pdf"
    
    def is_likely_datasheet(self, filepath: str, part_number: str) -> Tuple[bool, str]:
        """
        Analyze a PDF to determine if it's likely a datasheet.
        
        Args:
            filepath: Path to the downloaded PDF
            part_number: Component part number to check for
            
        Returns:
            tuple: (is_datasheet, reason)
        """
        try:
            # Check if the file exists
            if not os.path.exists(filepath):
                return False, "File does not exist"
                
            # Check file size (most datasheets are between 100KB and 10MB)
            file_size_kb = os.path.getsize(filepath) / 1024
            if file_size_kb < 50:
                return False, f"File too small ({file_size_kb:.1f}KB) - likely not a datasheet"
            if file_size_kb > 20000:
                return False, f"File too large ({file_size_kb:.1f}KB) - likely not a datasheet"
            
            # If PyMuPDF is not available, accept based on file size
            if fitz is None:
                logger.warning("PyMuPDF (fitz) not available, skipping content validation")
                return True, f"Accepted based on file size: {file_size_kb:.1f}KB (content validation skipped)"
                
            # Open the PDF
            pdf = fitz.open(filepath)
            
            # Check page count (most datasheets are between 3-200 pages)
            page_count = len(pdf)
            if page_count < 3:
                pdf.close()
                return False, f"Too few pages ({page_count}) - likely not a datasheet"
            if page_count > 200:
                pdf.close()
                return False, f"Too many pages ({page_count}) - likely not a datasheet"
            
            # Check first few pages to detect if it's a user guide or catalog
            exclusionary_terms = [
                "user guide", "user manual", "catalog", "product catalog", 
                "selection guide", "reference guide", "reference manual",
                "application note", "guide d'utilisation", "handbuch",
                "instruction manual", "programmer's guide", "programming guide"
            ]
            
            # Check title page and metadata for exclusionary terms
            for i in range(min(5, page_count)):
                page_text = pdf[i].get_text().lower()
                
                # If exclusionary terms found in first few pages, reject the PDF
                for term in exclusionary_terms:
                    if term in page_text:
                        pdf.close()
                        return False, f"Document appears to be a {term}, not a datasheet"
            
            # Check first page for datasheet terminology
            first_page_text = pdf[0].get_text().lower()
            datasheet_terms = [
                "datasheet", "technical data", "specifications", 
                "electrical characteristics", "block diagram", 
                "typical application", "pin configuration", "features",
                "absolute maximum ratings", "recommended operating conditions"
            ]
            
            term_found = any(term.lower() in first_page_text for term in datasheet_terms)
            
            # Check metadata for title containing 'datasheet'
            metadata = pdf.metadata
            title_is_datasheet = False
            if metadata and metadata.get('title'):
                title = metadata.get('title').lower()
                title_is_datasheet = "datasheet" in title or "data sheet" in title
                
                # Also check metadata title for exclusionary terms
                for term in exclusionary_terms:
                    if term in title:
                        pdf.close()
                        return False, f"Metadata title indicates this is a {term}, not a datasheet"
            
            pdf.close()
            
            if term_found or title_is_datasheet:
                return True, f"Datasheet identified: {page_count} pages, {file_size_kb:.1f}KB, contains datasheet terminology"
            
            # Accept as a datasheet if it has a typical datasheet page count
            if 5 <= page_count <= 100:
                return True, f"Likely datasheet based on format: {page_count} pages, {file_size_kb:.1f}KB"
            
            # More lenient approach - just accept any PDF with reasonable size and page count
            return True, f"Potential datasheet: {page_count} pages, {file_size_kb:.1f}KB"
                
        except Exception as e:
            logger.error(f"Error analyzing PDF: {str(e)}")
            return False, f"Error analyzing PDF: {str(e)}"

    def _try_google_search(self, search_term: str, use_filetype: bool = True) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """
        Search Google for PDF datasheets.
        
        Args:
            search_term: Search term (usually part number)
            use_filetype: Whether to add filetype:pdf to the search
            
        Returns:
            Tuple of (success, message, filepath, download_url)
        """
        if not self.page:
            return False, "Browser not started. Call 'start()' first.", None, None

        # Format the search query
        if use_filetype and "filetype:" not in search_term:
            search_query = f"{search_term} filetype:pdf"
        else:
            search_query = search_term

        try:
            # Go directly to Google search results instead of filling the search box
            # This avoids issues with cookie consent dialogs
            encoded_query = urllib.parse.quote(search_query)
            search_url = f"https://www.google.com/search?q={encoded_query}"
            logger.info(f"Navigating directly to search URL: {search_url}")
            
            self.page.goto(search_url, timeout=30000)
            time.sleep(random.uniform(1.0, 2.0))
            
            # Save a screenshot of the search results page for debugging
            os.makedirs("debug_screenshots", exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = f"debug_screenshots/search_{search_term.replace(' ', '_')}_{timestamp}.png"
            self.page.screenshot(path=screenshot_path)
            logger.info(f"Saved search results screenshot to: {screenshot_path}")
            
            # Wait for search results to load
            self.page.wait_for_selector('div#search', timeout=20000)
            
            # Skip the CAPTCHA handling section - let user handle manually if needed
            
            # Scroll down to load more results and simulate human behavior
            for _ in range(3):
                self.page.evaluate("window.scrollBy(0, 500)")
                time.sleep(random.uniform(0.5, 1.5))
            
            # Define known manufacturer domains
            manufacturer_domains = [
                # Semiconductor manufacturers
                "ti.com", "analog.com", "nxp.com", "microchip.com", 
                "st.com", "infineon.com", "vishay.com", "rohm.com", 
                "toshiba.com", "diodes.com", "onsemi.com", 
                "maximintegrated.com", "renesas.com", "issi.com",
                "cypress.com", "silabs.com", "xilinx.com", "intel.com",
                "amd.com", "skyworksinc.com", "nexperia.com", "latticesemi.com",
                
                # Major distributors (they usually host official datasheets)
                "mouser.com", "digikey.com", "arrow.com", "futureelectronics.com",
                "newark.com", "farnell.com", "element14.com", "avnet.com",
                "rs-online.com", "tme.eu", "reichelt.com", "lcsc.com",
                
                # Datasheet repositories with reliable content
                "alldatasheet.com", "datasheetq.com", "datasheet.octopart.com",
                "datasheets360.com", "datasheetspdf.com", "digchip.com"
            ]
            
            pdf_links = []
            
            # When using filetype:pdf, grab all main links from search results
            if use_filetype:
                # Get all search result containers
                search_results = self.page.query_selector_all('div.g, div.MjjYud, div.N54PNb')
                
                logger.info(f"Found {len(search_results)} search result containers")
                
                for result in search_results:
                    try:
                        # Grab the main link (usually the first link with a header/title)
                        links = result.query_selector_all('a:has(h3)')
                        if links and len(links) > 0:
                            pdf_links.append(links[0])
                            logger.debug(f"Found main link: {links[0].get_attribute('href')}")
                        else:
                            # If no link with h3, just get the first link
                            links = result.query_selector_all('a')
                            if links and len(links) > 0:
                                pdf_links.append(links[0])
                                logger.debug(f"Found alternative link: {links[0].get_attribute('href')}")
                    except Exception as e:
                        logger.debug(f"Error extracting link from search result: {str(e)}")
            
            # For non-filetype searches, look for PDF indicators or .pdf in URLs
            else:
                # Look for links that might be PDFs
                pdf_links = self.page.query_selector_all('a[href*=".pdf"]')
                
                # Also look for links with PDF badges
                pdf_badge_divs = self.page.query_selector_all('div:has-text("PDF"), div:has(span:text("PDF"))')
                
                # For each PDF badge, find the associated link
                for badge in pdf_badge_divs:
                    try:
                        # Navigate upwards to find the container and its main link
                        parent = badge
                        for _ in range(6):  # Try going up to 6 levels
                            if parent is None:
                                break
                            
                            links = parent.query_selector_all('a')
                            if links and len(links) > 0:
                                pdf_links.append(links[0])
                                break
                                
                            parent = parent.evaluate("node => node.parentNode")
                    except Exception as e:
                        logger.debug(f"Error finding link for PDF badge: {str(e)}")
            
            # If still no links found, try to find any links that might lead to PDFs
            if not pdf_links:
                logger.info("No PDF links found, trying to find any links that might lead to PDFs")
                # Look for links that might contain datasheet info
                possible_links = self.page.query_selector_all(
                    'a:has-text("datasheet"), a:has-text("Datasheet"), a:has-text("PDF"), a:has-text("pdf")'
                )
                if possible_links:
                    for link in possible_links[:3]:
                        try:
                            # Visit the link to look for PDFs there
                            href = link.get_attribute("href")
                            if href:
                                self.page.goto(href)
                                time.sleep(self.delay_seconds)
                                pdf_links = self.page.query_selector_all('a[href*=".pdf"]')
                                if pdf_links:
                                    break
                        except:
                            continue
            
            if pdf_links:
                # Sort PDF links: prioritize manufacturer domains first, then others
                manufacturer_pdfs = []
                other_pdfs = []
                
                # List to store all found PDF URLs for logging
                all_pdf_urls = []
                
                for link in pdf_links:
                    try:
                        pdf_url = link.get_attribute("href")
                        if not pdf_url or "googleusercontent" in pdf_url or "webcache" in pdf_url:
                            continue  # Skip Google's cached versions
                            
                        # Check if the URL is from a manufacturer domain
                        domain = urllib.parse.urlparse(pdf_url).netloc
                        is_manufacturer = any(mfr in domain for mfr in manufacturer_domains)
                        
                        # Add to the appropriate list
                        if is_manufacturer:
                            manufacturer_pdfs.append(pdf_url)
                        else:
                            other_pdfs.append(pdf_url)
                            
                        # Add to the all_pdf_urls list with priority info
                        all_pdf_urls.append({
                            "url": pdf_url,
                            "domain": domain,
                            "is_manufacturer": is_manufacturer,
                            "priority": "HIGH" if is_manufacturer else "LOW"
                        })
                    except Exception as e:
                        logger.debug(f"Error processing PDF link: {str(e)}")
                
                # Log all found PDF URLs
                logger.info(f"Found {len(all_pdf_urls)} potential PDF links:")
                for i, pdf_info in enumerate(all_pdf_urls):
                    logger.info(f"  {i+1}. [{pdf_info['priority']}] {pdf_info['domain']} - {pdf_info['url']}")
                
                # Combine lists with manufacturer PDFs first
                prioritized_pdfs = manufacturer_pdfs + other_pdfs
                
                logger.info(f"Prioritized order: {len(manufacturer_pdfs)} manufacturer PDFs, {len(other_pdfs)} other PDFs")
                
                # Extract part number from search term if it contains spaces
                part_number = search_term.split()[0] if " " in search_term else search_term
                
                # List to keep track of tried PDFs
                tried_pdfs = []
                
                # Try downloading PDFs in priority order - up to 10 PDFs
                for i, pdf_url in enumerate(prioritized_pdfs[:10]):
                    try:
                        # Skip if we've already tried this PDF
                        if pdf_url in tried_pdfs:
                            continue
                        
                        tried_pdfs.append(pdf_url)
                        logger.info(f"Trying PDF link {i+1}/{min(10, len(prioritized_pdfs))}: {pdf_url}")
                        
                        # Check if from manufacturer and log
                        domain = urllib.parse.urlparse(pdf_url).netloc
                        from_manufacturer = any(mfr in domain for mfr in manufacturer_domains)
                        if from_manufacturer:
                            logger.info(f"✅ PDF is from manufacturer/trusted domain: {domain}")

                        # Download the PDF
                        success, message, filepath, download_url = self.download_direct_pdf(pdf_url, part_number)
                        
                        if success:
                            # Check if the PDF is a datasheet
                            is_datasheet, reason = self.is_likely_datasheet(filepath, part_number)
                            
                            if is_datasheet:
                                source_type = "manufacturer/trusted site" if from_manufacturer else "other source"
                                logger.info(f"✅ Verified datasheet: {reason}")
                                return True, f"Successfully downloaded datasheet from {source_type}: {message}", filepath, download_url
                            else:
                                logger.info(f"❌ Downloaded PDF is not a datasheet: {reason}")
                                # Delete the file as it's not a datasheet
                                try:
                                    os.remove(filepath)
                                    logger.info(f"Deleted non-datasheet PDF: {filepath}")
                                except:
                                    pass
                                # Continue to try the next PDF
                    except Exception as e:
                        logger.debug(f"Error processing PDF link: {str(e)}")
                        continue
                
                # If we got here, we tried all PDFs but none were valid datasheets
                if tried_pdfs:
                    return False, f"Downloaded {len(tried_pdfs)} PDFs but none were valid datasheets", None, None
                    
        except Exception as e:
            logger.error(f"Error during Google search: {str(e)}")
            return False, f"Error during search: {str(e)}", None, None

        return False, "No suitable PDF found in search results", None, None
        
    def _try_direct_manufacturer_url(self, manufacturer: str, part_number: str) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """
        Try to download from manufacturer website.
        
        Args:
            manufacturer: Manufacturer key
            part_number: Component part number
            
        Returns:
            Tuple of (success, message, filepath, download_url)
        """
        if not self.page:
            return False, "Browser not started. Call 'start()' first.", None, None

        if manufacturer not in self.manufacturer_urls:
            return False, f"No URL template for manufacturer: {manufacturer}", None, None

        base_url = self.manufacturer_urls[manufacturer]

        try:
            if manufacturer == "ti":
                # Try direct PDF download using the symlink pattern
                normalized_part = self._normalize_ti_part(part_number)
                pdf_url = f"{base_url}{normalized_part}.pdf"

                logger.info(f"Trying direct TI datasheet URL: {pdf_url}")
                success, message, filepath, download_url = self.download_direct_pdf(pdf_url, part_number)
                if success:
                    return success, message, filepath, download_url

                # If direct download fails, try searching on TI's website
                search_url = f"https://www.ti.com/product/{part_number}"
                logger.info(f"Trying TI product page: {search_url}")

                self.page.goto(search_url, timeout=30000)
                time.sleep(self.delay_seconds)

                # Check for 404 error
                if "We can't find this page" in self.page.content():
                    logger.info("TI product page not found, trying search")
                    self.page.goto(f"https://www.ti.com/search?q={part_number}", timeout=30000)
                    time.sleep(self.delay_seconds)

                # Look for datasheet link
                datasheet_links = self.page.query_selector_all('a:has-text("Datasheet"), a[href*="pdf"]')

                if datasheet_links:
                    pdf_url = datasheet_links[0].get_attribute("href")
                    logger.info(f"Found TI datasheet URL: {pdf_url}")
                    return self.download_direct_pdf(pdf_url, part_number)

            elif manufacturer == "onsemi":
                search_url = f"{base_url}search?q={part_number}"
                self.page.goto(search_url, timeout=30000)
                time.sleep(self.delay_seconds)

                # Look for product link
                product_links = self.page.query_selector_all(f'a[href*="{part_number}"]:not([href*="pdf"])')

                if product_links:
                    self.page.goto(product_links[0].get_attribute("href"), timeout=30000)
                    time.sleep(self.delay_seconds)

                    # Look for datasheet link
                    datasheet_links = self.page.query_selector_all('a:has-text("Datasheet"), a[href*="pdf"]')

                    if datasheet_links:
                        pdf_url = datasheet_links[0].get_attribute("href")
                        logger.info(f"Found OnSemi datasheet URL: {pdf_url}")
                        return self.download_direct_pdf(pdf_url, part_number)

            elif manufacturer == "infineon":
                search_url = f"{base_url}search/{part_number}"
                self.page.goto(search_url, timeout=30000)
                time.sleep(self.delay_seconds)

                # Look for product link
                product_links = self.page.query_selector_all(f'a[href*="{part_number}"]')

                if product_links:
                    self.page.goto(product_links[0].get_attribute("href"), timeout=30000)
                    time.sleep(self.delay_seconds)

                    # Look for datasheet link
                    datasheet_links = self.page.query_selector_all(
                        'a:has-text("Datasheet"), a[href*="pdf"][href*="download"]'
                    )

                    if datasheet_links:
                        pdf_url = datasheet_links[0].get_attribute("href")
                        logger.info(f"Found Infineon datasheet URL: {pdf_url}")
                        return self.download_direct_pdf(pdf_url, part_number)

        except Exception as e:
            logger.error(f"Error trying direct manufacturer URL: {str(e)}")

        return False, "No datasheet found at manufacturer site", None, None
        
    def search_by_part_number(self, part_number: str) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """
        Search for a datasheet by part number and download it.
        
        Args:
            part_number: Component part number
            
        Returns:
            Tuple of (success, message, filepath, download_url)
        """
        if not self.page:
            return False, "Browser not started. Call 'start()' first.", None, None

        logger.info(f"Searching for datasheet for part number: {part_number}")

        # Start directly with Google search strategies instead of trying manufacturer identification first
        search_strategies = [
            # 1. Basic search with filetype specification
            f"{part_number} datasheet filetype:pdf",
            
            # 2. Identify manufacturer and search with manufacturer name
            self._get_manufacturer_specific_search(part_number),
            
            # 3. More specific search terms
            f"{part_number} technical documentation filetype:pdf",
            f"{part_number} specifications datasheet pdf",
            
            # 4. Try without filetype restriction as last resort
            f"{part_number} datasheet"
        ]
        
        # Filter out None values (in case manufacturer-specific search is None)
        search_strategies = [s for s in search_strategies if s]
        
        # Try each search strategy
        for search_term in search_strategies:
            logger.info(f"Trying search strategy: {search_term}")
            success, message, filepath, download_url = self._try_google_search(
                search_term, use_filetype="filetype:" in search_term
            )
            if success:
                return success, message, filepath, download_url
                
        # If all Google search strategies fail, only then try direct manufacturer download
        manufacturer = self._identify_manufacturer(part_number)
        if manufacturer:
            logger.info(f"Google search failed. Trying manufacturer: {manufacturer}")
            success, message, filepath, download_url = self._try_direct_manufacturer_url(manufacturer, part_number)
            if success:
                return success, message, filepath, download_url

        return False, "Could not find datasheet through any method", None, None
        
    def search_direct_sources(self, mpn: str) -> List[Dict[str, str]]:
        """
        Search for datasheets directly from manufacturer and distributor sites.
        This is a fallback method that doesn't depend on Google search.
        
        Args:
            mpn: Manufacturer Part Number of the component
            
        Returns:
            List of dictionaries containing datasheet information
        """
        logger.info(f"------------------------------{mpn}------------------------------")
        logger.info(f"Searching direct sources for: {mpn}")
        results = []
        
        # List of common electronics component sites with their search URLs
        direct_sources = [
            {
                'name': 'DigiKey',
                'url': f'https://www.digikey.com/en/products/filter?keywords={urllib.parse.quote(mpn)}',
                'datasheet_selector': 'a[data-testid="datasheet-download"]',
                'title_selector': 'h1.product-details-header-title'
            },
            {
                'name': 'Mouser',
                'url': f'https://www.mouser.com/c/?q={urllib.parse.quote(mpn)}',
                'datasheet_selector': 'a.pdp-tech-docs-link',
                'title_selector': 'h1.pdp-product-card-title'
            },
            {
                'name': 'Octopart',
                'url': f'https://octopart.com/search?q={urllib.parse.quote(mpn)}',
                'datasheet_selector': 'a[data-ga-event-action="Datasheet"]',
                'title_selector': 'h1.part-name'
            },
            {
                'name': 'Texas Instruments',
                'url': f'https://www.ti.com/sitesearch/en-us/docs/universalsearch.tsp?searchTerm={urllib.parse.quote(mpn)}',
                'datasheet_selector': 'a[href*="pdf"]',
                'title_selector': 'div.ti_search-results__result_name'
            },
            {
                'name': 'Analog Devices',
                'url': f'https://www.analog.com/en/search.html?q={urllib.parse.quote(mpn)}',
                'datasheet_selector': 'a[href*="pdf"]',
                'title_selector': '.search-product-title'
            }
        ]
        
        # Try each source
        for source in direct_sources:
            try:
                logger.info(f"Checking {source['name']} for {mpn}")
                self.page.goto(source['url'], timeout=20000)
                time.sleep(random.uniform(2.0, 4.0))  # Wait for page to load fully
                
                # Check if we found the component
                datasheet_links = self.page.query_selector_all(source['datasheet_selector'])
                
                if datasheet_links and len(datasheet_links) > 0:
                    # Get the first datasheet link
                    href = datasheet_links[0].get_attribute('href')
                    
                    # Get the title if possible
                    title_elem = self.page.query_selector(source['title_selector'])
                    title = title_elem.inner_text() if title_elem else f"{mpn} Datasheet from {source['name']}"
                    
                    if href:
                        # Convert relative URL to absolute if needed
                        if href.startswith('/'):
                            parsed_url = urllib.parse.urlparse(source['url'])
                            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                            href = base_url + href
                            
                        results.append({
                            'title': title,
                            'url': href,
                            'snippet': f"Datasheet found on {source['name']}",
                            'source': source['name'],
                            'mpn': mpn
                        })
                        
                        logger.info(f"Found datasheet on {source['name']}: {href}")
                
            except Exception as e:
                logger.warning(f"Error searching {source['name']}: {e}")
                continue
                
        return results
        
    def process_csv_file(self, csv_path: str):
        """
        Process a CSV file with part numbers and datasheet URLs.
        
        Args:
            csv_path: Path to the CSV file
        """
        # Read the CSV file
        try:
            df = pd.read_csv(csv_path)
            logger.info(f"Found {len(df)} rows in {csv_path}")
        except Exception as e:
            logger.error(f"Error reading CSV file: {str(e)}")
            return

        # Check for required columns
        required_columns = ["Datasheet URL", "MIME Type"]
        if not all(col in df.columns for col in required_columns):
            logger.error(f"Missing required columns in CSV: {required_columns}")
            return

        # Add a new column for downloaded URL if it doesn't exist
        if "Downloaded URL" not in df.columns:
            df["Downloaded URL"] = ""

        # Find the part number column
        part_number_column = None
        possible_columns = ["Part Number", "mpn", "MPN", "Model", "part_number"]
        for col in possible_columns:
            if col in df.columns:
                part_number_column = col
                break

        if not part_number_column:
            logger.warning("Could not find a column for part numbers, using row indices.")
            part_number_column = None

        # Create results list for summary
        results = []

        # Start the browser
        self.start()

        # Process each row
        for idx, row in tqdm(df.iterrows(), total=len(df)):
            part_number = row.get(part_number_column) if part_number_column else f"part_{idx}"
            datasheet_url = row.get("Datasheet URL")
            mime_type = row.get("MIME Type")

            logger.info(f"Processing {idx+1}/{len(df)}: {part_number}")

            success = False
            message = "Not processed"
            filepath = None
            download_url = None

            # Case 1: Direct PDF URL
            if pd.notna(datasheet_url) and pd.notna(mime_type) and "pdf" in str(mime_type).lower():
                logger.info(f"Direct PDF download: {datasheet_url}")
                success, message, filepath, download_url = self.download_direct_pdf(
                    datasheet_url, part_number
                )

            # Case 2: HTML page or missing URL - search by part number
            else:
                logger.info(f"Searching for PDF by part number: {part_number}")
                success, message, filepath, download_url = self.search_by_part_number(
                    part_number
                )

            # Update the original CSV with the download URL
            if success and download_url:
                df.at[idx, "Downloaded URL"] = download_url

            # Record the result for summary
            results.append(
                {
                    "Part Number": part_number,
                    "Original URL": datasheet_url if pd.notna(datasheet_url) else "",
                    "Downloaded URL": download_url if download_url else "",
                    "Success": success,
                    "Message": message,
                    "File Path": filepath or "",
                }
            )

            # Save the updated CSV after each successful download
            if success:
                df.to_csv(csv_path, index=False)
                logger.info(f"Updated CSV file with download URL for {part_number}")

            # Add a randomized delay between operations to avoid detection
            delay = self.delay_seconds + random.uniform(1, 3)
            time.sleep(delay)

        # Close the browser
        self.stop()

        # Final save of the CSV file
        df.to_csv(csv_path, index=False)
        logger.info(f"Final CSV file saved to: {csv_path}")

        # Create summary DataFrame and save to CSV
        results_df = pd.DataFrame(results)
        results_file = os.path.join(os.path.dirname(csv_path), "download_summary.csv")
        results_df.to_csv(results_file, index=False)

        # Print summary
        success_count = sum(1 for r in results if r["Success"])
        logger.info("\nDownload Summary:")
        logger.info(f"Total parts: {len(results)}")
        logger.info(f"Successfully downloaded: {success_count}")
        logger.info(f"Failed downloads: {len(results) - success_count}")
        logger.info(f"Detailed summary saved to: {results_file}")
        logger.info(f"Original CSV updated with download URLs: {csv_path}")
        
    def get_datasheet(self, mpn: str, download: bool = True, max_results: int = 5) -> Union[List[Dict[str, str]], str]:
        """
        Search for and optionally download a datasheet for the given MPN.
        
        Args:
            mpn: Manufacturer Part Number
            download: Whether to download the first result automatically
            max_results: Maximum number of results to return
            
        Returns:
            If download=True, returns the path to the downloaded file
            If download=False, returns a list of datasheet search results
        """
        if download:
            # Search and download
            success, message, filepath, download_url = self.search_by_part_number(mpn)
            if success:
                return filepath
            
            # If Google search fails, try direct sources
            logger.info(f"Google search failed for {mpn}, trying direct sources")
            results = self.search_direct_sources(mpn)
            
            if results:
                # Download the first result
                success, message, filepath, download_url = self.download_direct_pdf(results[0]['url'], mpn)
                if success:
                    return filepath
            
            return None
        else:
            # Just return search results
            manufacturer = self._identify_manufacturer(mpn)
            results = []
            
            # First try direct sources
            direct_results = self.search_direct_sources(mpn)
            if direct_results:
                results.extend(direct_results)
            
            # Then try Google search
            search_term = f"{mpn} datasheet filetype:pdf"
            self._try_google_search(search_term, use_filetype=True)
            
            # Extract PDF links from page
            pdf_links = self.page.query_selector_all('a[href*=".pdf"]')
            for link in pdf_links[:max_results]:
                try:
                    url = link.get_attribute('href')
                    if url:
                        title_elem = link.query_selector('h3') or link
                        title = title_elem.inner_text() if hasattr(title_elem, 'inner_text') else f"{mpn} Datasheet"
                        
                        # Get domain as source
                        domain = urllib.parse.urlparse(url).netloc
                        
                        results.append({
                            'title': title,
                            'url': url,
                            'snippet': "Found in search results",
                            'source': domain,
                            'mpn': mpn
                        })
                except Exception as e:
                    logger.debug(f"Error processing search result: {e}")
            
            # Limit results and return
            return results[:max_results]


def download_datasheet(mpn: str, download_dir: Optional[str] = None, headless: bool = True) -> str:
    """
    Convenience function to download a datasheet in one step.
    
    Args:
        mpn: Manufacturer Part Number
        download_dir: Directory to save the datasheet
        headless: Whether to run the browser in headless mode
        
    Returns:
        Path to the downloaded datasheet
    """
    with DatasheetDownloader(headless=headless, download_dir=download_dir) as downloader:
        return downloader.get_datasheet(mpn) 