"""
Foreclosure Complaint Document Downloader
Downloads only FORECLOSURE COMPLAINT documents with organized folder structure:
- Main folder: "Foreclosure_Documents"
- Subfolders: "{case_number}_{date}_{attorney_name}"
- Saves metadata as JSON file in each subfolder
"""

import os
import re
import json
import requests
import time
from urllib.parse import urljoin, parse_qs, urlparse
from datetime import datetime
from typing import List, Dict, Any
import logging
from case_details_parser import SummitCaseDetailsParser

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ForeclosureComplaintDownloader:
    """Downloads only FORECLOSURE COMPLAINT documents with organized structure"""
    
    def __init__(self, base_url="https://clerkweb.summitoh.net/PublicSite/", delay=2.0):
        self.base_url = base_url
        self.delay = delay
        self.session = requests.Session()
        self.main_folder = "Foreclosure_Documents"
        
        # Set headers to mimic a browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def clean_filename(self, text: str) -> str:
        """Clean text for use in filenames and folder names"""
        if not text:
            return "Unknown"
        
        # Remove special characters and replace spaces with underscores
        cleaned = re.sub(r'[<>:"/\\|?*]', '', text)
        cleaned = re.sub(r'\s+', '_', cleaned.strip())
        cleaned = re.sub(r'[,\.]', '', cleaned)
        
        # Limit length
        return cleaned[:50] if len(cleaned) > 50 else cleaned
    
    def extract_attorney_name(self, filed_by: str) -> str:
        """Extract clean attorney name from filed_by field"""
        if not filed_by:
            return "Unknown_Attorney"
        
        # Common patterns for attorney names
        # Remove common suffixes and clean up
        name = filed_by.strip()
        
        # Remove trailing commas and periods
        name = re.sub(r'[,\.]+$', '', name)
        
        # If it's a law firm or organization, try to extract individual name
        if ',' in name:
            # Often format is "LAST, FIRST" or "FIRM NAME, ATTORNEY"
            parts = name.split(',')
            if len(parts) >= 2:
                # Take the first two parts and clean them
                name = f"{parts[0].strip()}_{parts[1].strip()}"
        
        return self.clean_filename(name)
    
    def find_foreclosure_complaints(self, case_data: dict) -> List[dict]:
        """
        Find all FORECLOSURE COMPLAINT documents in the case data
        
        Args:
            case_data (dict): Parsed case data
            
        Returns:
            List of foreclosure complaint documents with metadata
        """
        foreclosure_complaints = []
        
        docket_entries = case_data.get('docket_entries', [])
        basic_info = case_data.get('basic_info', {})
        
        for entry in docket_entries:
            description = entry.get('description', '').upper()
            
            # Look for FORECLOSURE COMPLAINT in description
            if 'FORECLOSURE COMPLAINT' in description:
                
                # Extract metadata
                document_info = {
                    'case_number': basic_info.get('case_number', 'Unknown_Case'),
                    'case_caption': basic_info.get('case_caption', ''),
                    'judge': basic_info.get('judge', ''),
                    'case_type': basic_info.get('case_type', ''),
                    'file_date': basic_info.get('file_date', ''),
                    'entry_date': entry.get('date', ''),
                    'filed_by': entry.get('filed_by', ''),
                    'attorney_name': self.extract_attorney_name(entry.get('filed_by', '')),
                    'description': entry.get('description', ''),
                    'document_link': entry.get('document_link', ''),
                    'document_id': entry.get('document_id', ''),
                    'raw_document_id': entry.get('raw_document_id', ''),
                    'has_document': entry.get('has_document', False)
                }
                
                foreclosure_complaints.append(document_info)
        
        return foreclosure_complaints
    
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
            logger.error(f"Error converting URL {display_image_url}: {e}")
            return display_image_url
    
    def create_folder_structure(self, document_info: dict) -> str:
        """
        Create organized folder structure for the document
        
        Args:
            document_info (dict): Document metadata
            
        Returns:
            str: Path to the created subfolder
        """
        # Create main folder
        os.makedirs(self.main_folder, exist_ok=True)
        
        # Clean components for folder name
        case_number = self.clean_filename(document_info['case_number'])
        entry_date = self.clean_filename(document_info['entry_date'])
        attorney_name = document_info['attorney_name']
        
        # Create subfolder name: case_number_date_attorney
        subfolder_name = f"{case_number}_{entry_date}_{attorney_name}"
        subfolder_path = os.path.join(self.main_folder, subfolder_name)
        
        # Create subfolder
        os.makedirs(subfolder_path, exist_ok=True)
        
        return subfolder_path
    
    def save_metadata(self, document_info: dict, folder_path: str) -> bool:
        """Save document metadata as JSON file"""
        try:
            metadata_file = os.path.join(folder_path, "case_metadata.json")
            
            # Add download timestamp
            document_info['downloaded_at'] = datetime.now().isoformat()
            
            with open(metadata_file, 'w', encoding='utf-8') as file:
                json.dump(document_info, file, indent=2, ensure_ascii=False)
            
            logger.info(f"Metadata saved: {metadata_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving metadata: {e}")
            return False
    
    def download_foreclosure_complaint(self, document_info: dict) -> dict:
        """
        Download a single foreclosure complaint document
        
        Args:
            document_info (dict): Document metadata
            
        Returns:
            dict: Download results
        """
        result = {
            'case_number': document_info['case_number'],
            'attorney_name': document_info['attorney_name'],
            'date': document_info['entry_date'],
            'success': False,
            'folder_path': '',
            'pdf_path': '',
            'metadata_path': '',
            'error': None
        }
        
        try:
            # Check if document has a link
            if not document_info.get('has_document', False) or not document_info.get('document_link'):
                result['error'] = "No document link available"
                return result
            
            # Create folder structure
            folder_path = self.create_folder_structure(document_info)
            result['folder_path'] = folder_path
            
            # Save metadata
            self.save_metadata(document_info, folder_path)
            result['metadata_path'] = os.path.join(folder_path, "case_metadata.json")
            
            # Prepare PDF filename
            case_number = self.clean_filename(document_info['case_number'])
            pdf_filename = f"{case_number}_Foreclosure_Complaint.pdf"
            pdf_path = os.path.join(folder_path, pdf_filename)
            result['pdf_path'] = pdf_path
            
            # Skip if PDF already exists
            if os.path.exists(pdf_path):
                logger.info(f"PDF already exists: {pdf_filename}")
                result['success'] = True
                return result
            
            # Download PDF
            logger.info(f"Downloading foreclosure complaint for case: {document_info['case_number']}")
            
            pdf_url = self.convert_display_image_to_pdf_url(document_info['document_link'])
            
            response = self.session.get(pdf_url, timeout=30)
            
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '').lower()
                
                if 'pdf' in content_type or response.content.startswith(b'%PDF'):
                    with open(pdf_path, 'wb') as file:
                        file.write(response.content)
                    
                    logger.info(f"Successfully downloaded: {pdf_filename} ({len(response.content)} bytes)")
                    result['success'] = True
                    return result
                else:
                    # Try original DisplayImage.asp URL
                    logger.warning(f"Direct PDF failed, trying DisplayImage.asp for: {pdf_filename}")
                    
                    response = self.session.get(document_info['document_link'], timeout=30)
                    
                    if response.status_code == 200:
                        with open(pdf_path, 'wb') as file:
                            file.write(response.content)
                        
                        logger.info(f"Downloaded via DisplayImage.asp: {pdf_filename} ({len(response.content)} bytes)")
                        result['success'] = True
                        return result
            
            result['error'] = f"HTTP {response.status_code}"
            logger.error(f"Failed to download {pdf_filename}: HTTP {response.status_code}")
            
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Error downloading foreclosure complaint: {e}")
        
        return result
    
    def download_all_foreclosure_complaints(self, case_data: dict) -> dict:
        """
        Download all foreclosure complaint documents from case data
        
        Args:
            case_data (dict): Parsed case data
            
        Returns:
            dict: Download results summary
        """
        # Find all foreclosure complaints
        foreclosure_complaints = self.find_foreclosure_complaints(case_data)
        
        results = {
            'total_foreclosure_complaints': len(foreclosure_complaints),
            'successful_downloads': 0,
            'failed_downloads': 0,
            'download_details': []
        }
        
        if not foreclosure_complaints:
            logger.info("No foreclosure complaint documents found in case data")
            return results
        
        logger.info(f"Found {len(foreclosure_complaints)} foreclosure complaint document(s)")
        
        for i, complaint in enumerate(foreclosure_complaints, 1):
            logger.info(f"Processing foreclosure complaint {i}/{len(foreclosure_complaints)}")
            
            # Download the document
            download_result = self.download_foreclosure_complaint(complaint)
            
            results['download_details'].append(download_result)
            
            if download_result['success']:
                results['successful_downloads'] += 1
                logger.info(f"✓ Downloaded: {download_result['case_number']} - {download_result['attorney_name']}")
            else:
                results['failed_downloads'] += 1
                logger.error(f"✗ Failed: {download_result['case_number']} - {download_result.get('error', 'Unknown error')}")
            
            # Be respectful - add delay between downloads
            if i < len(foreclosure_complaints):
                time.sleep(self.delay)
        
        return results
    
    def save_download_report(self, results: dict, output_file: str = None) -> bool:
        """Save download results report"""
        try:
            if not output_file:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = f"foreclosure_download_report_{timestamp}.json"
            
            with open(output_file, 'w', encoding='utf-8') as file:
                json.dump(results, file, indent=2, ensure_ascii=False)
            
            logger.info(f"Download report saved: {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving download report: {e}")
            return False


def main():
    """Main function to parse case data and download foreclosure complaints"""
    
    # Initialize parser and downloader
    parser = SummitCaseDetailsParser()
    downloader = ForeclosureComplaintDownloader(delay=2.0)
    
    html_file = "response_body.html"
    
    try:
        print("=" * 60)
        print("FORECLOSURE COMPLAINT DOCUMENT DOWNLOADER")
        print("=" * 60)
        
        # Parse the HTML file
        print("Parsing case details...")
        case_data = parser.parse_html_file(html_file)
        
        if not case_data:
            print("Failed to parse case data")
            return
        
        # Print case summary
        basic_info = case_data.get('basic_info', {})
        print(f"\nCase Information:")
        print(f"  Case Number: {basic_info.get('case_number', 'N/A')}")
        print(f"  Case Caption: {basic_info.get('case_caption', 'N/A')}")
        print(f"  Judge: {basic_info.get('judge', 'N/A')}")
        print(f"  File Date: {basic_info.get('file_date', 'N/A')}")
        
        # Download foreclosure complaints
        print(f"\nSearching for FORECLOSURE COMPLAINT documents...")
        
        results = downloader.download_all_foreclosure_complaints(case_data)
        
        # Print results
        print(f"\n" + "=" * 60)
        print("DOWNLOAD RESULTS")
        print("=" * 60)
        print(f"Total Foreclosure Complaints Found: {results['total_foreclosure_complaints']}")
        print(f"Successful Downloads: {results['successful_downloads']}")
        print(f"Failed Downloads: {results['failed_downloads']}")
        
        # Show download details
        if results['download_details']:
            print(f"\nDownload Details:")
            for detail in results['download_details']:
                status = "✓" if detail['success'] else "✗"
                print(f"  {status} {detail['case_number']} - {detail['date']} - {detail['attorney_name']}")
                if detail['success']:
                    print(f"    Folder: {detail['folder_path']}")
                    print(f"    PDF: {os.path.basename(detail['pdf_path'])}")
                else:
                    print(f"    Error: {detail.get('error', 'Unknown error')}")
        
        # Save report
        downloader.save_download_report(results)
        
        print(f"\nAll files saved in 'Foreclosure_Documents' folder")
        print("Each case has its own subfolder with PDF and metadata JSON file")
        
    except Exception as e:
        print(f"Error in main: {e}")
        logger.error(f"Error in main: {e}")


if __name__ == "__main__":
    main()
