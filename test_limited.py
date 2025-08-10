#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from complete_automation import CompleteForeClosureAutomation
import logging

# Set up logging to show progress
logging.basicConfig(level=logging.INFO)

def test_limited_automation():
    """Test automation on just 3 cases to verify PDF downloads"""
    
    automation = CompleteForeClosureAutomation(headless=False)
    
    try:
        # Search for cases
        cases = automation.search_foreclosure_cases("08/08/2025")
        
        if not cases:
            print("No cases found")
            return
        
        print(f"Found {len(cases)} cases, testing first 3...")
        
        # Process only first 3 cases
        test_cases = cases[:3]
        successful_downloads = 0
        
        for i, case in enumerate(test_cases, 1):
            print(f"\n=== Processing case {i}/3: {case['case_number']} ===")
            
            try:
                success = automation.process_single_case(case)
                if success:
                    print(f"✓ Case {case['case_number']} processed successfully")
                    
                    # Check what was downloaded
                    folder_name = f"{case['case_number']}_{case['date'].replace('/', '_')}"
                    folder_path = os.path.join("Foreclosure_Cases_Data", folder_name)
                    
                    if os.path.exists(folder_path):
                        files = os.listdir(folder_path)
                        pdf_files = [f for f in files if f.endswith('.pdf')]
                        html_files = [f for f in files if f.endswith('.html')]
                        
                        print(f"  Downloaded files:")
                        for file in files:
                            filepath = os.path.join(folder_path, file)
                            size = os.path.getsize(filepath)
                            print(f"    {file}: {size} bytes")
                            
                            if file.endswith('.pdf'):
                                # Verify it's a real PDF
                                with open(filepath, 'rb') as f:
                                    content = f.read(10)
                                    if content.startswith(b'%PDF'):
                                        print(f"      ✓ Valid PDF")
                                        successful_downloads += 1
                                    else:
                                        print(f"      ✗ Invalid PDF")
                else:
                    print(f"✗ Case {case['case_number']} failed")
                    
            except Exception as e:
                print(f"✗ Error processing case {case['case_number']}: {e}")
        
        print(f"\n=== Test Summary ===")
        print(f"Cases processed: {len(test_cases)}")
        print(f"Successful PDF downloads: {successful_downloads}")
        print(f"Success rate: {successful_downloads}/{len(test_cases)} = {(successful_downloads/len(test_cases)*100):.1f}%")
        
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        automation.cleanup()

if __name__ == "__main__":
    test_limited_automation()
