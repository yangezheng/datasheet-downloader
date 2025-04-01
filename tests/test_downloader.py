"""
Tests for the datasheet downloader package
"""

import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from datasheet_downloader import DatasheetDownloader


class TestDatasheetDownloader(unittest.TestCase):
    """Test cases for the DatasheetDownloader class"""
    
    @patch('datasheet_downloader.downloader.sync_playwright')
    def test_search_datasheet(self, mock_playwright):
        """Test searching for datasheets"""
        # Mock Playwright
        mock_page = MagicMock()
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_playwright.return_value.start.return_value.chromium.launch.return_value = mock_browser
        
        # Mock query results
        mock_link = MagicMock()
        mock_link.get_attribute.return_value = "http://example.com/datasheet.pdf"
        
        mock_title = MagicMock()
        mock_title.inner_text.return_value = "Example Datasheet"
        
        mock_snippet = MagicMock()
        mock_snippet.inner_text.return_value = "This is a datasheet for LM358"
        
        mock_result_element = MagicMock()
        mock_result_element.query_selector.side_effect = lambda selector: {
            'a': mock_link,
            'h3': mock_title,
            'div.VwiC3b': mock_snippet
        }.get(selector)
        
        mock_page.query_selector_all.return_value = [mock_result_element]
        
        # Test with the mocked objects
        with DatasheetDownloader(headless=True) as downloader:
            results = downloader.search_datasheet("LM358")
            
            # Verify correct URL was used
            mock_page.goto.assert_called_once()
            call_args = mock_page.goto.call_args[0][0]
            self.assertIn("LM358", call_args)
            self.assertIn("datasheet", call_args)
            self.assertIn("pdf", call_args)
            
            # Verify results are parsed correctly
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]['title'], "Example Datasheet")
            self.assertEqual(results[0]['url'], "http://example.com/datasheet.pdf")
            self.assertEqual(results[0]['snippet'], "This is a datasheet for LM358")
            self.assertEqual(results[0]['source'], "example.com")
            self.assertEqual(results[0]['mpn'], "LM358")
    
    @patch('datasheet_downloader.downloader.requests.get')
    def test_download_file(self, mock_get):
        """Test downloading a file"""
        # Mock the requests response
        mock_response = MagicMock()
        mock_response.headers.get.return_value = '1000'
        mock_response.iter_content.return_value = [b'test data']
        mock_get.return_value = mock_response
        
        # Create a temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            with DatasheetDownloader(download_dir=temp_dir) as downloader:
                output_path = downloader.download_file("http://example.com/datasheet.pdf")
                
                # Verify the file was downloaded
                self.assertTrue(os.path.exists(output_path))
                with open(output_path, 'rb') as f:
                    self.assertEqual(f.read(), b'test data')
                
                # Verify the request was made correctly
                mock_get.assert_called_once_with("http://example.com/datasheet.pdf", stream=True)


if __name__ == '__main__':
    unittest.main() 