#!/usr/bin/env python3
"""
Test script to read Excel files from the health insurance data directory
"""

import pandas as pd
import os

def test_excel_reading():
    """Test reading Excel files from the data directory"""
    
    # Base directory
    base_dir = "data"
    
    # Find all Excel files
    excel_files = []
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith(('.xlsx', '.xls')):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, base_dir)
                excel_files.append((rel_path, full_path))
    
    print(f"Found {len(excel_files)} Excel files:")
    for rel_path, full_path in excel_files:
        print(f"  - {rel_path}")
    
    # Test reading each file
    for rel_path, full_path in excel_files[:3]:  # Test first 3 files
        print(f"\nTesting: {rel_path}")
        try:
            # Read Excel file
            df = pd.read_excel(full_path)
            print(f"  Shape: {df.shape}")
            print(f"  Columns: {df.columns.tolist()}")
            print(f"  First 2 rows:")
            print(df.head(2))
            print("  ✓ Success")
        except Exception as e:
            print(f"  ✗ Error: {e}")

if __name__ == "__main__":
    test_excel_reading()