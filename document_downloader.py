"""
Summit County Document Downloader
Downloads all PDF documents from the case details and converts DisplayImage.asp URLs to direct PDF URLs
"""

import os
import requests
import time
from urllib.parse import urljoin, parse_qs, urlparse
import logging
from case_details_parser import SummitCaseDetailsParser

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SummitDocumentDownloader:
    """Downloads documents from Summit County case details"""
    
    def __init__(self, base_url="https://clerkweb.summitoh.net/PublicSite/", delay=1.0):
        self.base_url = base_url
        self.delay = delay  # Delay between downloads to be respectful
        self.session = requests.Session()
        
        # Set headers to mimic a browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def convert_display_image_to_pdf_url(self, display_image_url: str) -> str:
        """
        Convert DisplayImage.asp URL to direct PDF URL
        
        Args:
            display_image_url (str): The DisplayImage.asp URL
            
        Returns:
            str: Direct PDF URL
        """
        try:
            # Parse the URL to get the gstrPDFOH parameter
            parsed_url = urlparse(display_image_url)
            query_params = parse_qs(parsed_url.query)
            
            if 'gstrPDFOH' in query_params:
                pdf_id = query_params['gstrPDFOH'][0].strip()
                
                # Remove all spaces from the PDF ID to create clean filename
                # Example: "vola00000038        0000092C" becomes "vola000000380000092C"
                clean_pdf_id = pdf_id.replace(' ', '')
                
                # The PDF URL pattern appears to be:
                # https://clerkweb.summitoh.net/PublicSite/Documents/{clean_pdf_id}.pdf
                pdf_url = urljoin(self.base_url, f"Documents/{clean_pdf_id}.pdf")
                return pdf_url
            
            return display_image_url
            
        except Exception as e:
            logger.error(f"Error converting URL {display_image_url}: {e}")
            return display_image_url
    
    def download_document(self, url: str, filename: str, output_dir: str = "downloaded_documents") -> bool:
        """
        Download a single document
        
        Args:
            url (str): URL of the document
            filename (str): Filename to save as
            output_dir (str): Directory to save the document
            
        Returns:
            bool: Success status
        """
        try:
            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            
            filepath = os.path.join(output_dir, filename)
            
            # Skip if file already exists
            if os.path.exists(filepath):
                logger.info(f"File already exists: {filename}")
                return True
            
            logger.info(f"Downloading: {filename}")
            
            # Try direct PDF URL first
            pdf_url = self.convert_display_image_to_pdf_url(url)
            
            response = self.session.get(pdf_url, timeout=30)
            
            if response.status_code == 200:
                # Check if the response is actually a PDF
                content_type = response.headers.get('content-type', '').lower()
                
                if 'pdf' in content_type or response.content.startswith(b'%PDF'):
                    with open(filepath, 'wb') as file:
                        file.write(response.content)
                    
                    logger.info(f"Successfully downloaded: {filename} ({len(response.content)} bytes)")
                    return True
                else:
                    # If not PDF, try the original DisplayImage.asp URL
                    logger.warning(f"Direct PDF URL failed, trying DisplayImage.asp for: {filename}")
                    
                    response = self.session.get(url, timeout=30)
                    
                    if response.status_code == 200:
                        with open(filepath, 'wb') as file:
                            file.write(response.content)
                        
                        logger.info(f"Downloaded via DisplayImage.asp: {filename} ({len(response.content)} bytes)")
                        return True
            
            logger.error(f"Failed to download {filename}: HTTP {response.status_code}")
            return False
            
        except Exception as e:
            logger.error(f"Error downloading {filename}: {e}")
            return False
    
    def download_all_case_documents(self, case_data: dict, case_number: str = None) -> dict:
        """
        Download all documents from a case
        
        Args:
            case_data (dict): Parsed case data from SummitCaseDetailsParser
            case_number (str): Case number for folder naming
            
        Returns:
            dict: Download results
        """
        if not case_number:
            case_number = case_data.get('basic_info', {}).get('case_number', 'unknown_case')
        
        # Clean case number for folder name
        clean_case_number = "".join(c for c in case_number if c.isalnum() or c in ('-', '_')).strip()
        output_dir = f"downloaded_documents/{clean_case_number}"
        
        documents = case_data.get('documents', [])
        results = {
            'total_documents': len(documents),
            'successful_downloads': 0,
            'failed_downloads': 0,
            'download_details': []
        }
        
        logger.info(f"Starting download of {len(documents)} documents for case {case_number}")
        
        for i, doc in enumerate(documents, 1):
            url = doc.get('link', '')
            doc_id = doc.get('document_id', f'doc_{i}')
            
            # Create filename
            filename = f"{doc_id}.pdf"
            
            # Add context to filename if available
            context = doc.get('context', '').strip()
            if context:
                # Take first 50 chars of context and clean it
                clean_context = "".join(c for c in context[:50] if c.isalnum() or c in (' ', '-', '_')).strip()
                clean_context = clean_context.replace(' ', '_')
                filename = f"{doc_id}_{clean_context}.pdf"
            
            success = self.download_document(url, filename, output_dir)
            
            download_info = {
                'index': i,
                'document_id': doc_id,
                'filename': filename,
                'url': url,
                'success': success
            }
            
            results['download_details'].append(download_info)
            
            if success:
                results['successful_downloads'] += 1
            else:
                results['failed_downloads'] += 1
            
            # Be respectful - add delay between downloads
            if i < len(documents):
                time.sleep(self.delay)
        
        logger.info(f"Download complete: {results['successful_downloads']}/{results['total_documents']} successful")
        
        return results
    
    def save_download_report(self, results: dict, output_file: str) -> bool:
        """Save download results to a file"""
        try:
            import json
            with open(output_file, 'w', encoding='utf-8') as file:
                json.dump(results, file, indent=2, ensure_ascii=False)
            
            logger.info(f"Download report saved to: {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving download report: {e}")
            return False


def main():
    """Main function to parse HTML and download all documents"""
    
    # Initialize parser and downloader
    parser = SummitCaseDetailsParser()
    downloader = SummitDocumentDownloader(delay=2.0)  # 2 second delay between downloads
    
    html_file = "response_body.html"
    
    try:
        print("Parsing case details and downloading documents...")
        
        # Parse the HTML file
        case_data = parser.parse_html_file(html_file)
        
        if not case_data:
            print("Failed to parse case data")
            return
        
        # Print summary
        parser.print_summary()
        
        # Download all documents
        print(f"\nStarting download of {len(case_data.get('documents', []))} documents...")
        
        results = downloader.download_all_case_documents(case_data)
        
        # Print download results
        print(f"\nDownload Results:")
        print(f"Total Documents: {results['total_documents']}")
        print(f"Successful Downloads: {results['successful_downloads']}")
        print(f"Failed Downloads: {results['failed_downloads']}")
        
        # Save download report
        report_file = f"download_report_{case_data.get('basic_info', {}).get('case_number', 'unknown').replace('-', '_')}_{int(time.time())}.json"
        downloader.save_download_report(results, report_file)
        
        # List some of the downloaded files
        if results['successful_downloads'] > 0:
            print(f"\nSample downloaded files:")
            for detail in results['download_details'][:5]:
                if detail['success']:
                    print(f"  ✓ {detail['filename']}")
        
        # List failed downloads if any
        if results['failed_downloads'] > 0:
            print(f"\nFailed downloads:")
            for detail in results['download_details']:
                if not detail['success']:
                    print(f"  ✗ {detail['filename']} - {detail['url']}")
    
    except Exception as e:
        print(f"Error in main: {e}")


if __name__ == "__main__":
    main()
