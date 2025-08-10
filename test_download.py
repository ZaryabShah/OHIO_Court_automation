#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from complete_automation import CompleteForeClosureAutomation
import json

def test_single_download():
    """Test downloading a single document to debug the issue"""
    
    automation = CompleteForeClosureAutomation(headless=False)
    
    try:
        # Navigate to the website first to establish session
        automation.driver.get("https://clerkweb.summitoh.net/PublicSite/")
        
        # Test document info from case CV-2025-08-3686 that failed
        test_document = {
            'document_link': 'https://clerkweb.summitoh.net/PublicSite/DisplayImage.asp?gstrPDFOH=vola00000046        00001EA1',
            'document_id': 'vola0000004600001EA1'
        }
        
        # Create test folder
        test_folder = "test_download"
        os.makedirs(test_folder, exist_ok=True)
        
        print(f"Testing download of document: {test_document['document_id']}")
        print(f"Document URL: {test_document['document_link']}")
        
        # Try to download
        success = automation.download_foreclosure_complaint(test_document, test_folder)
        
        if success:
            print("✓ Download successful!")
            
            # Check what was downloaded
            files = os.listdir(test_folder)
            for file in files:
                filepath = os.path.join(test_folder, file)
                file_size = os.path.getsize(filepath)
                print(f"  Downloaded: {file} ({file_size} bytes)")
                
                if file.endswith('.pdf'):
                    # Check if it's a valid PDF
                    with open(filepath, 'rb') as f:
                        content = f.read(100)
                        if content.startswith(b'%PDF'):
                            print(f"  ✓ Valid PDF file")
                        else:
                            print(f"  ✗ Not a valid PDF file")
        else:
            print("✗ Download failed!")
        
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            automation.cleanup()
        except:
            pass

if __name__ == "__main__":
    test_single_download()
