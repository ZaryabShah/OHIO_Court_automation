"""
Summit County Court Records - Complete Integration
Combines scraping, parsing, and document downloading into one comprehensive tool
"""

import os
import json
import time
from datetime import datetime, timedelta
import argparse
import logging
from typing import List, Dict, Optional

from summit_county_scraper import SummitCountyScraper
from case_details_parser import SummitCaseDetailsParser
from document_downloader import SummitDocumentDownloader

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SummitCountyCompleteAutomation:
    """Complete automation for Summit County court records"""
    
    def __init__(self, headless=True, delay=2.0):
        self.scraper = SummitCountyScraper(headless=headless)
        self.parser = SummitCaseDetailsParser()
        self.downloader = SummitDocumentDownloader(delay=delay)
        self.results_dir = "automation_results"
        
        # Create results directory
        os.makedirs(self.results_dir, exist_ok=True)
    
    def search_and_process_foreclosures(self, date_str: str, download_docs=True) -> Dict:
        """
        Complete workflow: search, parse, and optionally download documents
        
        Args:
            date_str (str): Date in mm/dd/yyyy format
            download_docs (bool): Whether to download documents
            
        Returns:
            Dict: Complete results
        """
        results = {
            'search_date': date_str,
            'timestamp': datetime.now().isoformat(),
            'search_results': None,
            'cases': [],
            'total_cases': 0,
            'total_documents': 0,
            'download_results': {}
        }
        
        try:
            # Step 1: Search for foreclosure records
            logger.info(f"Searching for foreclosure records on {date_str}")
            search_html = self.scraper.search_foreclosure_records(date_str, save_to_file=True)
            
            if not search_html:
                logger.error("Failed to get search results")
                return results
            
            # Step 2: Parse search results to get case numbers
            case_links = self._extract_case_links_from_search(search_html)
            results['total_cases'] = len(case_links)
            
            logger.info(f"Found {len(case_links)} cases")
            
            # Step 3: Process each case
            for i, case_info in enumerate(case_links, 1):
                logger.info(f"Processing case {i}/{len(case_links)}: {case_info['case_number']}")
                
                case_result = self._process_single_case(
                    case_info['case_number'], 
                    case_info['link'], 
                    download_docs
                )
                
                if case_result:
                    results['cases'].append(case_result)
                    results['total_documents'] += case_result.get('document_count', 0)
                
                # Be respectful - delay between cases
                if i < len(case_links):
                    time.sleep(1)
            
            # Step 4: Save complete results
            self._save_complete_results(results, date_str)
            
            logger.info(f"Processing complete: {len(results['cases'])} cases processed")
            
        except Exception as e:
            logger.error(f"Error in complete workflow: {e}")
        
        finally:
            # Always close the browser
            self.scraper.close()
        
        return results
    
    def _extract_case_links_from_search(self, html_content: str) -> List[Dict]:
        """Extract case numbers and links from search results"""
        from bs4 import BeautifulSoup
        import re
        
        case_links = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find the results table
            results_table = soup.find('table', id=re.compile(r'.*gvMixedResults'))
            
            if results_table:
                rows = results_table.find_all('tr')
                
                for row in rows:
                    # Look for case number links
                    case_link = row.find('a', href=re.compile(r'CaseDetail\.aspx'))
                    
                    if case_link:
                        case_number = case_link.get_text(strip=True)
                        case_url = case_link['href']
                        
                        # Get case caption from the same row
                        cells = row.find_all('td')
                        case_caption = ""
                        if len(cells) >= 3:
                            case_caption = cells[2].get_text(strip=True)
                        
                        case_links.append({
                            'case_number': case_number,
                            'link': case_url,
                            'case_caption': case_caption
                        })
        
        except Exception as e:
            logger.error(f"Error extracting case links: {e}")
        
        return case_links
    
    def _process_single_case(self, case_number: str, case_url: str, download_docs=True) -> Optional[Dict]:
        """Process a single case: get details, parse, and optionally download documents"""
        
        try:
            # Navigate to case details page
            full_url = f"https://clerkweb.summitoh.net/PublicSite/{case_url}"
            self.scraper.driver.get(full_url)
            time.sleep(3)
            
            # Get case details HTML
            case_html = self.scraper.driver.page_source
            
            # Save case HTML
            case_html_file = os.path.join(self.results_dir, f"{case_number.replace('-', '_')}_details.html")
            with open(case_html_file, 'w', encoding='utf-8') as f:
                f.write(case_html)
            
            # Parse case details
            case_data = self.parser.parse_html_content(case_html)
            
            if not case_data:
                logger.error(f"Failed to parse case data for {case_number}")
                return None
            
            # Save parsed data
            case_json_file = os.path.join(self.results_dir, f"{case_number.replace('-', '_')}_data.json")
            with open(case_json_file, 'w', encoding='utf-8') as f:
                json.dump(case_data, f, indent=2, ensure_ascii=False)
            
            result = {
                'case_number': case_number,
                'case_data': case_data,
                'document_count': len(case_data.get('documents', [])),
                'html_file': case_html_file,
                'json_file': case_json_file,
                'download_result': None
            }
            
            # Download documents if requested
            if download_docs and case_data.get('documents'):
                logger.info(f"Downloading {len(case_data['documents'])} documents for {case_number}")
                
                download_result = self.downloader.download_all_case_documents(case_data, case_number)
                result['download_result'] = download_result
                
                # Save download report
                download_report_file = os.path.join(self.results_dir, f"{case_number.replace('-', '_')}_download_report.json")
                self.downloader.save_download_report(download_result, download_report_file)
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing case {case_number}: {e}")
            return None
    
    def _save_complete_results(self, results: Dict, date_str: str):
        """Save complete automation results"""
        try:
            # Create summary without full case data to avoid huge files
            summary = {
                'search_date': results['search_date'],
                'timestamp': results['timestamp'],
                'total_cases': results['total_cases'],
                'total_documents': results['total_documents'],
                'cases_summary': []
            }
            
            for case in results['cases']:
                case_summary = {
                    'case_number': case['case_number'],
                    'document_count': case['document_count'],
                    'html_file': case['html_file'],
                    'json_file': case['json_file']
                }
                
                if case['download_result']:
                    case_summary['downloads'] = {
                        'total': case['download_result']['total_documents'],
                        'successful': case['download_result']['successful_downloads'],
                        'failed': case['download_result']['failed_downloads']
                    }
                
                summary['cases_summary'].append(case_summary)
            
            # Save summary
            summary_file = os.path.join(self.results_dir, f"automation_summary_{date_str.replace('/', '_')}.json")
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Automation summary saved to: {summary_file}")
            
        except Exception as e:
            logger.error(f"Error saving complete results: {e}")
    
    def search_date_range(self, start_date: str, end_date: str, download_docs=True) -> List[Dict]:
        """
        Search multiple dates in a range
        
        Args:
            start_date (str): Start date in mm/dd/yyyy format
            end_date (str): End date in mm/dd/yyyy format
            download_docs (bool): Whether to download documents
            
        Returns:
            List of results for each date
        """
        from datetime import datetime, timedelta
        
        results = []
        
        try:
            start = datetime.strptime(start_date, "%m/%d/%Y")
            end = datetime.strptime(end_date, "%m/%d/%Y")
            
            current = start
            while current <= end:
                date_str = current.strftime("%m/%d/%Y")
                logger.info(f"Processing date: {date_str}")
                
                date_results = self.search_and_process_foreclosures(date_str, download_docs)
                results.append(date_results)
                
                current += timedelta(days=1)
                
                # Longer delay between different dates
                time.sleep(5)
            
        except Exception as e:
            logger.error(f"Error in date range search: {e}")
        
        return results


def main():
    """Main function with command line interface"""
    
    parser = argparse.ArgumentParser(description='Summit County Court Records Automation')
    parser.add_argument('--date', type=str, help='Search date (mm/dd/yyyy)', 
                       default=datetime.now().strftime("%m/%d/%Y"))
    parser.add_argument('--start-date', type=str, help='Start date for range search (mm/dd/yyyy)')
    parser.add_argument('--end-date', type=str, help='End date for range search (mm/dd/yyyy)')
    parser.add_argument('--no-download', action='store_true', help='Skip document downloads')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    parser.add_argument('--delay', type=float, default=2.0, help='Delay between downloads (seconds)')
    
    args = parser.parse_args()
    
    try:
        automation = SummitCountyCompleteAutomation(
            headless=args.headless, 
            delay=args.delay
        )
        
        download_docs = not args.no_download
        
        if args.start_date and args.end_date:
            # Date range search
            print(f"Searching date range: {args.start_date} to {args.end_date}")
            results = automation.search_date_range(args.start_date, args.end_date, download_docs)
            
            print(f"\nCompleted date range search:")
            for result in results:
                print(f"  {result['search_date']}: {result['total_cases']} cases, {result['total_documents']} documents")
        
        else:
            # Single date search
            search_date = args.date
            print(f"Searching for foreclosure records on: {search_date}")
            
            results = automation.search_and_process_foreclosures(search_date, download_docs)
            
            print(f"\nSearch Results Summary:")
            print(f"Date: {results['search_date']}")
            print(f"Total Cases: {results['total_cases']}")
            print(f"Total Documents: {results['total_documents']}")
            print(f"Successfully Processed: {len(results['cases'])} cases")
            
            if download_docs:
                total_successful_downloads = sum(
                    case.get('download_result', {}).get('successful_downloads', 0) 
                    for case in results['cases']
                )
                print(f"Total Downloads: {total_successful_downloads}")
    
    except KeyboardInterrupt:
        print("\nAutomation interrupted by user")
    
    except Exception as e:
        print(f"Error in automation: {e}")


if __name__ == "__main__":
    main()
