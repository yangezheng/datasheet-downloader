"""
Tests for the CLI module
"""

import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from datasheet_downloader.cli import main, parse_args


class TestCLI(unittest.TestCase):
    """Test cases for the CLI module"""
    
    def test_parse_args(self):
        """Test argument parsing"""
        # Test with MPN argument
        args = parse_args(["LM358"])
        self.assertEqual(args.mpn, "LM358")
        self.assertFalse(args.list_only)
        self.assertFalse(args.no_headless)
        self.assertEqual(args.output_dir, os.getcwd())
        
        # Test with output dir
        args = parse_args(["LM358", "-o", "/tmp/datasheets"])
        self.assertEqual(args.output_dir, "/tmp/datasheets")
        
        # Test with list only
        args = parse_args(["LM358", "--list-only"])
        self.assertTrue(args.list_only)
        
        # Test with file input
        args = parse_args(["-f", "mpns.txt"])
        self.assertEqual(args.file, "mpns.txt")
    
    @patch('datasheet_downloader.cli.DatasheetDownloader')
    def test_main_with_mpn(self, mock_downloader_cls):
        """Test main function with MPN"""
        # Mock the downloader
        mock_downloader = MagicMock()
        mock_downloader_cls.return_value.__enter__.return_value = mock_downloader
        mock_downloader.get_datasheet.return_value = "/tmp/datasheets/lm358.pdf"
        
        # Call main with test args
        exit_code = main(["LM358", "-o", "/tmp/datasheets"])
        
        # Verify downloader was called correctly
        self.assertEqual(exit_code, 0)
        mock_downloader.get_datasheet.assert_called_once_with("LM358")
    
    @patch('datasheet_downloader.cli.DatasheetDownloader')
    def test_main_with_file(self, mock_downloader_cls):
        """Test main function with file input"""
        # Create a temp file with MPNs
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write("LM358\nATmega328P\n")
            temp_file_name = temp_file.name
            
        try:
            # Mock the downloader
            mock_downloader = MagicMock()
            mock_downloader_cls.return_value.__enter__.return_value = mock_downloader
            mock_downloader.get_datasheet.side_effect = [
                "/tmp/datasheets/lm358.pdf",
                "/tmp/datasheets/atmega328p.pdf"
            ]
            
            # Call main with test args
            exit_code = main(["-f", temp_file_name, "-o", "/tmp/datasheets"])
            
            # Verify downloader was called correctly
            self.assertEqual(exit_code, 0)
            self.assertEqual(mock_downloader.get_datasheet.call_count, 2)
            mock_downloader.get_datasheet.assert_any_call("LM358")
            mock_downloader.get_datasheet.assert_any_call("ATmega328P")
        finally:
            # Clean up temp file
            os.unlink(temp_file_name)
    
    @patch('datasheet_downloader.cli.DatasheetDownloader')
    def test_main_list_only(self, mock_downloader_cls):
        """Test main function with list-only option"""
        # Mock the downloader
        mock_downloader = MagicMock()
        mock_downloader_cls.return_value.__enter__.return_value = mock_downloader
        mock_downloader.get_datasheet.return_value = [
            {
                'title': 'LM358 Datasheet',
                'url': 'http://example.com/lm358.pdf',
                'source': 'example.com',
                'snippet': 'Datasheet for LM358',
                'mpn': 'LM358'
            }
        ]
        
        # Call main with test args
        exit_code = main(["LM358", "--list-only"])
        
        # Verify downloader was called correctly
        self.assertEqual(exit_code, 0)
        mock_downloader.get_datasheet.assert_called_once_with("LM358", download=False)


if __name__ == '__main__':
    unittest.main() 