#!/usr/bin/env python3

import sys
from enhanced_pdf_parser import extract_text_any

def debug_pdf_text(file_path):
    """Debug PDF text extraction to understand the format"""
    text = extract_text_any(file_path)
    
    print("=== RAW TEXT SAMPLE (first 2000 chars) ===")
    print(text[:2000])
    print("\n" + "="*50)
    
    print("\n=== LINES CONTAINING 'PLAINTIFF' ===")
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if 'plaintiff' in line.lower():
            # Show context around the line
            start = max(0, i-2)
            end = min(len(lines), i+3)
            print(f"Lines {start}-{end}:")
            for j in range(start, end):
                marker = " >>> " if j == i else "     "
                print(f"{marker}{j}: {lines[j]}")
            print()
    
    print("\n=== LINES CONTAINING '-VS-' ===")
    for i, line in enumerate(lines):
        if '-vs-' in line.lower():
            start = max(0, i-2)
            end = min(len(lines), i+3)
            print(f"Lines {start}-{end}:")
            for j in range(start, end):
                marker = " >>> " if j == i else "     "
                print(f"{marker}{j}: {lines[j]}")
            print()
    
    print("\n=== LINES CONTAINING 'RUSHMORE' ===")
    for i, line in enumerate(lines):
        if 'rushmore' in line.lower():
            start = max(0, i-2)
            end = min(len(lines), i+3)
            print(f"Lines {start}-{end}:")
            for j in range(start, end):
                marker = " >>> " if j == i else "     "
                print(f"{marker}{j}: {lines[j]}")
            print()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python debug_pdf.py <pdf_file>")
        sys.exit(1)
    
    debug_pdf_text(sys.argv[1])
