"""
Unit tests for data_loader module.
"""

import unittest
import pandas as pd
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_loader import load_raw_data, save_processed_data


class TestDataLoader(unittest.TestCase):
    """Test cases for data loading functions."""

    def test_load_raw_data_file_not_found(self):
        """Test that FileNotFoundError is raised for non-existent files."""
        with self.assertRaises(FileNotFoundError):
            load_raw_data("non_existent_file.csv")

    def test_unsupported_format(self):
        """Test that ValueError is raised for unsupported file formats."""
        with self.assertRaises(ValueError):
            load_raw_data("data.txt")


if __name__ == "__main__":
    unittest.main()
