"""
Complete Summit County Foreclosure Automation Pipeline
Continuously monitors for new foreclosure cases and downloads documents.

Features:
- Finds all foreclosure cases for today
- Downloads case details and foreclosure complaints
- Organizes data in case-specific folders
- Tracks processed cases to avoid duplicates
- Runs continuously with 1-hour intervals
- Keeps browser open for document downloads
- Enhanced PDF parsing with structured data extraction
"""

import os
import json
import time
import logging
import requests
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Set, Optional
from urllib.parse import urljoin, parse_qs, urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys

from bs4 import BeautifulSoup

# Import enhanced PDF parser
from enhanced_pdf_parser import parse_pdf

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('foreclosure_automation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class CompleteForeClosureAutomation:
    """Complete automation pipeline for Summit County foreclosure cases"""
    
    def __init__(self, headless=False, check_interval_hours=0.5):
        self.base_url = "https://clerkweb.summitoh.net/PublicSite/"
        self.check_interval = check_interval_hours * 3600  # Convert to seconds
        self.headless = headless
        
        # Initialize selenium driver
        self.driver = None
        self.wait = None
        
        # Initialize requests session for API calls
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # Storage
        self.processed_cases_file = "processed_cases.json"
        self.main_data_folder = "Foreclosure_Cases_Data"
        self.processed_cases: Set[str] = set()
        
        # Create main folder
        os.makedirs(self.main_data_folder, exist_ok=True)
        
        # Load processed cases
        self.load_processed_cases()
        
        # Setup browser
        self.setup_browser()
    
    def setup_browser(self):
        """Initialize Chrome WebDriver"""
        try:
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # PDF handling preferences
            prefs = {
                'plugins.always_open_pdf_externally': False,  # View PDFs in browser
                'plugins.plugins_disabled': [],
                'profile.default_content_settings.popups': 0,
                'profile.default_content_setting_values.automatic_downloads': 1
            }
            chrome_options.add_experimental_option('prefs', prefs)
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 15)
            
            logger.info("Browser initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing browser: {e}")
            raise
    
    def load_processed_cases(self):
        """Load previously processed cases"""
        try:
            if os.path.exists(self.processed_cases_file):
                with open(self.processed_cases_file, 'r') as f:
                    data = json.load(f)
                    self.processed_cases = set(data.get('processed_cases', []))
                logger.info(f"Loaded {len(self.processed_cases)} previously processed cases")
            else:
                self.processed_cases = set()
                logger.info("No previous processed cases found")
        except Exception as e:
            logger.error(f"Error loading processed cases: {e}")
            self.processed_cases = set()
    
    def save_processed_cases(self):
        """Save processed cases to file"""
        try:
            data = {
                'last_updated': datetime.now().isoformat(),
                'processed_cases': list(self.processed_cases)
            }
            with open(self.processed_cases_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved {len(self.processed_cases)} processed cases")
        except Exception as e:
            logger.error(f"Error saving processed cases: {e}")
    
    def search_foreclosure_cases(self, date_str: str) -> List[Dict]:
        """Search for foreclosure cases on a specific date"""
        try:
            logger.info(f"Searching for foreclosure cases on {date_str}")
            
            # Navigate to search page
            self.driver.get("https://clerkweb.summitoh.net/PublicSite/SelectDivisionCivil.aspx")
            time.sleep(2)
            
            self.driver.get("https://clerkweb.summitoh.net/PublicSite/SearchByMixed.aspx")
            time.sleep(2)
            
            # Enter date
            date_input = self.wait.until(
                EC.presence_of_element_located((
                    By.XPATH, 
                    "/html/body/table[2]/tbody/tr[1]/td/form/table[2]/tbody/tr/td/table/tbody/tr[3]/td[2]/input"
                ))
            )
            date_input.clear()
            date_input.send_keys(date_str)
            
            # Select Foreclosure
            dropdown = self.wait.until(
                EC.presence_of_element_located((
                    By.XPATH,
                    "/html/body/table[2]/tbody/tr[1]/td/form/table[2]/tbody/tr/td/table/tbody/tr[7]/td[2]/select"
                ))
            )
            Select(dropdown).select_by_visible_text("Foreclosure")
            
            # Click search
            search_button = self.wait.until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "/html/body/table[2]/tbody/tr[1]/td/form/table[3]/tbody/tr/td/input[1]"
                ))
            )
            search_button.click()
            
            time.sleep(3)
            
            # Parse results
            html_content = self.driver.page_source
            cases = self.parse_search_results(html_content)
            
            logger.info(f"Found {len(cases)} cases for {date_str}")
            return cases
            
        except Exception as e:
            logger.error(f"Error searching for cases: {e}")
            return []
    
    def parse_search_results(self, html_content: str) -> List[Dict]:
        """Parse search results HTML to extract case information"""
        cases = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find results table
            results_table = soup.find('table', id=lambda x: x and 'gvMixedResults' in x)
            
            if results_table:
                rows = results_table.find_all('tr')
                
                for row in rows:
                    # Look for case number link
                    case_link = row.find('a', href=lambda x: x and 'CaseDetail.aspx' in x)
                    
                    if case_link:
                        case_number = case_link.get_text(strip=True)
                        case_url = case_link['href']
                        
                        # Get additional info from row
                        cells = row.find_all('td')
                        filing_date = ""
                        case_caption = ""
                        
                        if len(cells) >= 3:
                            filing_date = cells[0].get_text(strip=True)
                            case_caption = cells[2].get_text(strip=True)
                        
                        case_info = {
                            'case_number': case_number,
                            'filing_date': filing_date,
                            'case_caption': case_caption,
                            'case_url': case_url,
                            'full_url': urljoin(self.base_url, case_url)
                        }
                        
                        cases.append(case_info)
        
        except Exception as e:
            logger.error(f"Error parsing search results: {e}")
        
        return cases
    
    def create_case_folder(self, case_info: Dict) -> str:
        """Create folder for case data"""
        case_number = case_info['case_number']
        filing_date = case_info.get('filing_date', 'unknown_date')
        
        # Clean for folder name
        clean_case_number = re.sub(r'[<>:"/\\|?*]', '_', case_number)
        clean_date = re.sub(r'[<>:"/\\|?*]', '_', filing_date)
        
        folder_name = f"{clean_case_number}_{clean_date}"
        folder_path = os.path.join(self.main_data_folder, folder_name)
        
        os.makedirs(folder_path, exist_ok=True)
        
        logger.info(f"Created folder: {folder_path}")
        return folder_path
    
    def get_case_details(self, case_info: Dict) -> Optional[Dict]:
        """Get detailed case information"""
        try:
            logger.info(f"Getting details for case: {case_info['case_number']}")
            
            # Navigate to case details page
            self.driver.get(case_info['full_url'])
            time.sleep(3)
            
            # Click on the specified element to access documents
            try:
                document_tab = self.wait.until(
                    EC.element_to_be_clickable((
                        By.XPATH,
                        "/html/body/table[2]/tbody/tr[1]/td/form/table/tbody/tr/td/table/tbody/tr[2]/td/table/tbody/tr[3]/td/div/table/tbody/tr[1]/td/table/tbody/tr/td[2]"
                    ))
                )
                document_tab.click()
                logger.info("Clicked on document tab")
                time.sleep(2)  # Wait 2 seconds as requested
                
            except Exception as e:
                logger.warning(f"Could not click document tab: {e}")
            
            # Get page HTML after clicking
            html_content = self.driver.page_source
            
            # Parse case details
            case_details = self.parse_case_details(html_content, case_info)
            
            return case_details
            
        except Exception as e:
            logger.error(f"Error getting case details for {case_info['case_number']}: {e}")
            return None
    
    def parse_case_details(self, html_content: str, case_info: Dict) -> Dict:
        """Parse case details HTML"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        case_data = {
            'basic_info': {},
            'parties': {'plaintiffs': [], 'defendants': []},
            'docket_entries': [],
            'documents': [],
            'metadata': {
                'parsed_at': datetime.now().isoformat(),
                'source_url': case_info['full_url']
            }
        }
        
        try:
            # Basic case info
            case_caption = soup.find('span', id='ContentPlaceHolder1_lblCaseCaption')
            case_number = soup.find('span', id='ContentPlaceHolder1_lblCaseNumber')
            file_date = soup.find('span', id='ContentPlaceHolder1_lblFileDate')
            case_type = soup.find('span', id='ContentPlaceHolder1_lblCaseType')
            judge = soup.find('span', id='ContentPlaceHolder1_lblJudgeName')
            
            case_data['basic_info'] = {
                'case_caption': case_caption.get_text(strip=True) if case_caption else "",
                'case_number': case_number.get_text(strip=True) if case_number else case_info['case_number'],
                'file_date': file_date.get_text(strip=True) if file_date else case_info.get('filing_date', ''),
                'case_type': case_type.get_text(strip=True) if case_type else "FORECLOSURE",
                'judge': judge.get_text(strip=True) if judge else ""
            }
            
            # Extract docket entries
            docket_table = soup.find('table', id=lambda x: x and 'gvDocketDetails' in x)
            if docket_table:
                rows = docket_table.find_all('tr')
                
                for row in rows:
                    if 'GridViewPlainRow' in row.get('class', []):
                        cells = row.find_all('td')
                        if len(cells) >= 4:
                            # Extract document link
                            doc_cell = cells[3]
                            doc_link = doc_cell.find('a', href=lambda x: x and 'DisplayImage.asp' in x)
                            
                            entry = {
                                'date': cells[0].get_text(strip=True),
                                'filed_by': cells[1].get_text(strip=True),
                                'description': cells[2].get_text(strip=True),
                                'has_document': bool(doc_link),
                                'document_link': "",
                                'document_id': ""
                            }
                            
                            if doc_link:
                                entry['document_link'] = urljoin(self.base_url, doc_link['href'])
                                # Extract clean document ID
                                match = re.search(r'gstrPDFOH=([^&]+)', doc_link['href'])
                                if match:
                                    raw_id = match.group(1)
                                    entry['document_id'] = raw_id.replace(' ', '')
                                    entry['raw_document_id'] = raw_id
                            
                            case_data['docket_entries'].append(entry)
            
            # Update metadata
            case_data['metadata']['total_docket_entries'] = len(case_data['docket_entries'])
            
        except Exception as e:
            logger.error(f"Error parsing case details: {e}")
        
        return case_data
    
    def find_foreclosure_complaint(self, case_data: Dict) -> Optional[Dict]:
        """Find foreclosure complaint document in case data"""
        for entry in case_data.get('docket_entries', []):
            description = entry.get('description', '').upper()
            if 'FORECLOSURE COMPLAINT' in description and entry.get('has_document'):
                return entry
        return None
    
    def download_foreclosure_complaint(self, document_info: Dict, folder_path: str) -> bool:
        """Download foreclosure complaint PDF using browser session cookies"""
        try:
            if not document_info.get('document_link'):
                logger.warning("No document link available")
                return False
            
            logger.info(f"Downloading foreclosure complaint: {document_info['document_id']}")
            
            # Get all cookies from the current browser session
            browser_cookies = self.driver.get_cookies()
            
            # Create a new requests session with browser cookies
            download_session = requests.Session()
            download_session.headers.update({
                'User-Agent': self.driver.execute_script("return navigator.userAgent;"),
                'Accept': 'application/pdf,application/octet-stream,*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            })
            
            # Add all browser cookies to the session
            for cookie in browser_cookies:
                download_session.cookies.set(
                    name=cookie['name'],
                    value=cookie['value'],
                    domain=cookie.get('domain', ''),
                    path=cookie.get('path', '/'),
                    secure=cookie.get('secure', False)
                )
            
            # Try direct PDF URL first
            pdf_url = self.convert_display_image_to_pdf_url(document_info['document_link'])
            logger.info(f"Trying PDF URL: {pdf_url}")
            
            try:
                response = download_session.get(pdf_url, timeout=30, allow_redirects=True)
                logger.info(f"PDF URL response: {response.status_code}, Content-Type: {response.headers.get('content-type')}, Size: {len(response.content)}")
                
                if response.status_code == 200 and len(response.content) > 1000:
                    if 'pdf' in response.headers.get('content-type', '').lower() or response.content.startswith(b'%PDF'):
                        filename = f"{document_info['document_id']}_Foreclosure_Complaint.pdf"
                        filepath = os.path.join(folder_path, filename)
                        
                        with open(filepath, 'wb') as f:
                            f.write(response.content)
                        
                        logger.info(f"Successfully downloaded PDF: {filename} ({len(response.content)} bytes)")
                        
                        # Parse the downloaded PDF
                        self.parse_downloaded_pdf(filepath, folder_path)
                        
                        return True
            except Exception as e:
                logger.warning(f"PDF URL failed: {e}")
            
            # Try DisplayImage URL if PDF URL failed
            logger.info(f"Trying DisplayImage URL: {document_info['document_link']}")
            
            try:
                response = download_session.get(document_info['document_link'], timeout=30, allow_redirects=True)
                logger.info(f"DisplayImage response: {response.status_code}, Content-Type: {response.headers.get('content-type')}, Size: {len(response.content)}")
                
                if response.status_code == 200 and len(response.content) > 1000:
                    if 'pdf' in response.headers.get('content-type', '').lower() or response.content.startswith(b'%PDF'):
                        filename = f"{document_info['document_id']}_Foreclosure_Complaint.pdf"
                        filepath = os.path.join(folder_path, filename)
                        
                        with open(filepath, 'wb') as f:
                            f.write(response.content)
                        
                        logger.info(f"Successfully downloaded PDF via DisplayImage: {filename} ({len(response.content)} bytes)")
                        
                        # Parse the downloaded PDF
                        self.parse_downloaded_pdf(filepath, folder_path)
                        
                        return True
                    else:
                        # Content is not PDF, save as HTML
                        filename = f"{document_info['document_id']}_Foreclosure_Complaint.html"
                        filepath = os.path.join(folder_path, filename)
                        
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(response.text)
                        
                        logger.info(f"Downloaded non-PDF content as HTML: {filename}")
                        return True
            except Exception as e:
                logger.warning(f"DisplayImage URL failed: {e}")
            
            logger.error("All download methods failed")
            return False
            
        except Exception as e:
            logger.error(f"Error downloading document: {e}")
            return False
    
    def convert_display_image_to_pdf_url(self, display_image_url: str) -> str:
        """Convert DisplayImage.asp URL to direct PDF URL"""
        try:
            parsed_url = urlparse(display_image_url)
            query_params = parse_qs(parsed_url.query)
            
            if 'gstrPDFOH' in query_params:
                pdf_id = query_params['gstrPDFOH'][0].strip()
                clean_pdf_id = pdf_id.replace(' ', '')
                pdf_url = urljoin(self.base_url, f"Documents/{clean_pdf_id}.pdf")
                return pdf_url
            
            return display_image_url
            
        except Exception as e:
            logger.error(f"Error converting URL: {e}")
            return display_image_url
    
    def parse_downloaded_pdf(self, pdf_filepath: str, case_folder: str) -> bool:
        """Parse downloaded PDF using enhanced parser and save results"""
        try:
            logger.info(f"Parsing PDF: {pdf_filepath}")
            
            # Use the enhanced PDF parser
            parsed_data = parse_pdf(pdf_filepath)
            
            # Save parsed data as JSON
            parsed_filename = "foreclosure_complaint_parsed.json"
            parsed_filepath = os.path.join(case_folder, parsed_filename)
            
            with open(parsed_filepath, 'w', encoding='utf-8') as f:
                json.dump(parsed_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Successfully parsed and saved PDF data: {parsed_filepath}")
            
            # Log key extracted information
            logger.info(f"  Plaintiff: {parsed_data.get('plaintiff', 'Not found')}")
            logger.info(f"  Defendants: {len(parsed_data.get('defendants', []))} found")
            logger.info(f"  Property Address: {parsed_data.get('property_address', 'Not found')}")
            logger.info(f"  Redemption Price: ${parsed_data.get('redemption_price', 'Not found')}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error parsing PDF {pdf_filepath}: {e}")
            return False
    
    def save_case_data(self, case_data: Dict, folder_path: str):
        """Save case data to JSON file"""
        try:
            filename = "case_details.json"
            filepath = os.path.join(folder_path, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(case_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved case data: {filepath}")
            
        except Exception as e:
            logger.error(f"Error saving case data: {e}")
    
    def save_case_metadata(self, case_info: Dict, case_data: Dict, download_result: bool, folder_path: str):
        """Save case metadata"""
        try:
            # Check if PDF was parsed
            parsed_file = os.path.join(folder_path, "foreclosure_complaint_parsed.json")
            pdf_parsed = os.path.exists(parsed_file)
            
            metadata = {
                'case_number': case_info['case_number'],
                'case_caption': case_info.get('case_caption', ''),
                'filing_date': case_info.get('filing_date', ''),
                'processed_at': datetime.now().isoformat(),
                'folder_path': folder_path,
                'case_url': case_info['full_url'],
                'has_case_details': bool(case_data),
                'foreclosure_complaint_downloaded': download_result,
                'foreclosure_complaint_parsed': pdf_parsed,
                'total_docket_entries': len(case_data.get('docket_entries', [])) if case_data else 0
            }
            
            filename = "case_metadata.json"
            filepath = os.path.join(folder_path, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved case metadata: {filepath}")
            
        except Exception as e:
            logger.error(f"Error saving case metadata: {e}")
    
    def process_single_case(self, case_info: Dict) -> bool:
        """Process a single case: get details and download documents"""
        case_number = case_info['case_number']
        
        try:
            logger.info(f"Processing case: {case_number}")
            
            # Create folder for this case
            folder_path = self.create_case_folder(case_info)
            
            # Get case details
            case_data = self.get_case_details(case_info)
            
            if not case_data:
                logger.error(f"Failed to get case details for {case_number}")
                return False
            
            # Save case details
            self.save_case_data(case_data, folder_path)
            
            # Find and download foreclosure complaint
            foreclosure_doc = self.find_foreclosure_complaint(case_data)
            download_result = False
            
            if foreclosure_doc:
                download_result = self.download_foreclosure_complaint(foreclosure_doc, folder_path)
            else:
                logger.warning(f"No foreclosure complaint found for {case_number}")
            
            # Save metadata
            self.save_case_metadata(case_info, case_data, download_result, folder_path)
            
            # Mark as processed
            self.processed_cases.add(case_number)
            self.save_processed_cases()
            
            logger.info(f"Successfully processed case: {case_number}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing case {case_number}: {e}")
            return False
    
    def process_all_cases(self, cases: List[Dict]) -> Dict:
        """Process all found cases"""
        results = {
            'total_cases': len(cases),
            'new_cases': 0,
            'successfully_processed': 0,
            'pdfs_downloaded': 0,
            'pdfs_parsed': 0,
            'failed_cases': []
        }
        
        for case_info in cases:
            case_number = case_info['case_number']
            
            # Skip if already processed
            if case_number in self.processed_cases:
                logger.info(f"Case {case_number} already processed, skipping")
                continue
            
            results['new_cases'] += 1
            
            # Process the case
            success = self.process_single_case(case_info)
            
            if success:
                results['successfully_processed'] += 1
                
                # Check if PDF was downloaded and parsed
                case_folder = self.create_case_folder(case_info)
                pdf_files = [f for f in os.listdir(case_folder) if f.endswith('.pdf')]
                parsed_files = [f for f in os.listdir(case_folder) if f == 'foreclosure_complaint_parsed.json']
                
                if pdf_files:
                    results['pdfs_downloaded'] += 1
                if parsed_files:
                    results['pdfs_parsed'] += 1
            else:
                results['failed_cases'].append(case_number)
            
            # Add delay between cases to be respectful
            time.sleep(2)
        
        return results
    
    def run_continuous_monitoring(self):
        """Run continuous monitoring for new foreclosure cases"""
        logger.info("Starting continuous foreclosure monitoring...")
        
        try:
            while True:
                # Get today's date
                # today = datetime.now().strftime("%m/%d/%Y")
                today = "08/08/2025"
                logger.info(f"Starting monitoring cycle for {today}")
                
                try:
                    # Search for cases
                    cases = self.search_foreclosure_cases(today)
                    
                    if cases:
                        # Process all cases
                        results = self.process_all_cases(cases)
                        
                        logger.info(f"Monitoring cycle complete:")
                        logger.info(f"  Total cases found: {results['total_cases']}")
                        logger.info(f"  New cases: {results['new_cases']}")
                        logger.info(f"  Successfully processed: {results['successfully_processed']}")
                        logger.info(f"  PDFs downloaded: {results['pdfs_downloaded']}")
                        logger.info(f"  PDFs parsed: {results['pdfs_parsed']}")
                        logger.info(f"  Failed cases: {len(results['failed_cases'])}")
                        
                        if results['failed_cases']:
                            logger.warning(f"Failed to process: {', '.join(results['failed_cases'])}")
                    
                    else:
                        logger.info("No cases found for today")
                
                except Exception as e:
                    logger.error(f"Error in monitoring cycle: {e}")
                
                # Wait for next check
                logger.info(f"Waiting {self.check_interval/3600:.1f} hours before next check...")
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        
        except Exception as e:
            logger.error(f"Fatal error in monitoring: {e}")
        
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        try:
            if self.driver:
                self.driver.quit()
                logger.info("Browser closed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


def main():
    """Main function to start the automation"""
    
    # Configuration
    HEADLESS_MODE = False  # Set to True to run without browser window
    CHECK_INTERVAL_HOURS = 1  # How often to check for new cases
    
    try:
        logger.info("="*60)
        logger.info("SUMMIT COUNTY FORECLOSURE AUTOMATION STARTING")
        logger.info("="*60)
        
        # Initialize automation
        automation = CompleteForeClosureAutomation(
            headless=HEADLESS_MODE,
            check_interval_hours=CHECK_INTERVAL_HOURS
        )
        
        # Start monitoring
        automation.run_continuous_monitoring()
        
    except KeyboardInterrupt:
        logger.info("\nAutomation stopped by user")
    
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    
    finally:
        logger.info("Foreclosure automation ended")


if __name__ == "__main__":
    main()
