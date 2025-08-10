"""
Test script to download a single case document to debug PDF download issues
"""

import os
import json
import time
import logging
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_chrome_for_pdf():
    """Setup Chrome with PDF-friendly options"""
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # PDF handling preferences
    prefs = {
        'plugins.always_open_pdf_externally': False,  # View PDFs in browser
        'plugins.plugins_disabled': [],
        'profile.default_content_settings.popups': 0,
        'profile.default_content_setting_values.automatic_downloads': 1
    }
    options.add_experimental_option('prefs', prefs)
    
    return webdriver.Chrome(options=options)

def convert_display_image_to_pdf_url(display_url: str) -> str:
    """Convert DisplayImage.asp URL to PDF URL"""
    try:
        if 'DisplayImage.asp' in display_url:
            # Replace DisplayImage.asp with DisplayDocument.asp
            pdf_url = display_url.replace('DisplayImage.asp', 'DisplayDocument.asp')
            return pdf_url
        return display_url
    except Exception as e:
        logger.error(f"Error converting URL: {e}")
        return display_url

def test_document_download():
    """Test downloading a specific document"""
    driver = setup_chrome_for_pdf()
    
    try:
        # Test with a known case document
        test_case = "CV-2025-08-3687"
        document_id = "vola0000004600001EAF"
        
        # Read the case details to get the document link
        case_folder = f"Foreclosure_Cases_Data/{test_case}_08_08_2025"
        case_details_file = os.path.join(case_folder, "case_details.json")
        
        if os.path.exists(case_details_file):
            with open(case_details_file, 'r') as f:
                case_data = json.load(f)
            
            # Find the foreclosure complaint
            document_info = None
            for entry in case_data.get('docket_entries', []):
                if entry.get('document_id') == document_id:
                    document_info = entry
                    break
            
            if document_info:
                logger.info(f"Testing download of: {document_info['document_id']}")
                
                # Try direct PDF URL
                pdf_url = convert_display_image_to_pdf_url(document_info['document_link'])
                logger.info(f"PDF URL: {pdf_url}")
                
                # Try with browser session
                driver.get("https://clerkweb.summitoh.net/PublicSite/")
                time.sleep(2)
                
                # Navigate to the PDF URL
                driver.get(pdf_url)
                time.sleep(8)  # Wait for PDF to load
                
                current_url = driver.current_url
                logger.info(f"Current URL: {current_url}")
                
                # Check page source
                page_source = driver.page_source
                logger.info(f"Page source length: {len(page_source)}")
                
                # Always save page source for inspection
                with open(f"debug_{document_id}.html", 'w', encoding='utf-8') as f:
                    f.write(page_source)
                logger.info(f"Saved debug file: debug_{document_id}.html")
                
                if len(page_source) > 500:  # Any significant content
                    logger.info("Page has content")
                    
                    # Try to extract PDF content if it's embedded
                    if 'pdf' in page_source.lower() or 'embed' in page_source.lower():
                        logger.info("PDF/embed content detected in page")
                        
                        # Get cookies for authenticated session
                        cookies = {cookie['name']: cookie['value'] for cookie in driver.get_cookies()}
                        logger.info(f"Got {len(cookies)} cookies")
                        
                        # Try download with session cookies
                        session = requests.Session()
                        session.cookies.update(cookies)
                        
                        response = session.get(pdf_url)
                        logger.info(f"Response status: {response.status_code}")
                        logger.info(f"Response headers: {dict(response.headers)}")
                        logger.info(f"Response content length: {len(response.content)}")
                        
                        if response.content.startswith(b'%PDF'):
                            logger.info("Valid PDF content found!")
                            with open(f"test_{document_id}.pdf", 'wb') as f:
                                f.write(response.content)
                        else:
                            logger.info("Response is not a PDF")
                            logger.info(f"First 200 chars: {response.content[:200]}")
                    else:
                        logger.info("No PDF/embed content detected")
                
            else:
                logger.error(f"Document {document_id} not found in case data")
        else:
            logger.error(f"Case details file not found: {case_details_file}")
            
    except Exception as e:
        logger.error(f"Error during test: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    test_document_download()
