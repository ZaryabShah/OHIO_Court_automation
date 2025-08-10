"""
Summit County Case Details HTML Parser
Extracts comprehensive case information from HTML files including:
- Case basic information
- Plaintiff and defendant details
- Docket entries with document links
- Service records
- Document links and metadata
"""

import re
import json
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin
from typing import Dict, List, Optional, Any
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SummitCaseDetailsParser:
    """Parser for Summit County case details HTML files"""
    
    def __init__(self, base_url="https://clerkweb.summitoh.net/PublicSite/"):
        self.base_url = base_url
        self.case_data = {}
    
    def parse_html_file(self, file_path: str) -> Dict[str, Any]:
        """
        Parse HTML file and extract all case information
        
        Args:
            file_path (str): Path to the HTML file
            
        Returns:
            Dict containing all parsed case information
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                html_content = file.read()
            
            return self.parse_html_content(html_content)
            
        except Exception as e:
            logger.error(f"Error reading HTML file: {e}")
            return {}
    
    def parse_html_content(self, html_content: str) -> Dict[str, Any]:
        """
        Parse HTML content and extract all case information
        
        Args:
            html_content (str): HTML content as string
            
        Returns:
            Dict containing all parsed case information
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            self.case_data = {
                'basic_info': self._extract_basic_case_info(soup),
                'parties': self._extract_parties_info(soup),
                'docket_entries': self._extract_docket_entries(soup),
                'judges_magistrates': self._extract_judges_magistrates(soup),
                'service_records': self._extract_service_records(soup),
                'documents': self._extract_all_documents(soup),
                'metadata': {
                    'parsed_at': datetime.now().isoformat(),
                    'total_docket_entries': 0,
                    'total_documents': 0,
                    'total_service_records': 0
                }
            }
            
            # Update metadata counts
            self.case_data['metadata']['total_docket_entries'] = len(self.case_data['docket_entries'])
            self.case_data['metadata']['total_documents'] = len(self.case_data['documents'])
            self.case_data['metadata']['total_service_records'] = len(self.case_data['service_records'])
            
            logger.info(f"Successfully parsed case data with {self.case_data['metadata']['total_docket_entries']} docket entries")
            
            return self.case_data
            
        except Exception as e:
            logger.error(f"Error parsing HTML content: {e}")
            return {}
    
    def _extract_basic_case_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract basic case information"""
        basic_info = {}
        
        try:
            # Case caption
            case_caption = soup.find('span', id='ContentPlaceHolder1_lblCaseCaption')
            basic_info['case_caption'] = case_caption.get_text(strip=True) if case_caption else ""
            
            # Case number
            case_number = soup.find('span', id='ContentPlaceHolder1_lblCaseNumber')
            basic_info['case_number'] = case_number.get_text(strip=True) if case_number else ""
            
            # File date
            file_date = soup.find('span', id='ContentPlaceHolder1_lblFileDate')
            basic_info['file_date'] = file_date.get_text(strip=True) if file_date else ""
            
            # Case type
            case_type = soup.find('span', id='ContentPlaceHolder1_lblCaseType')
            basic_info['case_type'] = case_type.get_text(strip=True) if case_type else ""
            
            # Judge
            judge = soup.find('span', id='ContentPlaceHolder1_lblJudgeName')
            basic_info['judge'] = judge.get_text(strip=True) if judge else ""
            
        except Exception as e:
            logger.error(f"Error extracting basic case info: {e}")
        
        return basic_info
    
    def _extract_parties_info(self, soup: BeautifulSoup) -> Dict[str, List[Dict]]:
        """Extract plaintiff and defendant information"""
        parties = {'plaintiffs': [], 'defendants': []}
        
        try:
            # Extract plaintiffs
            plaintiff_table = soup.find('table', id=re.compile(r'.*gvPlaintiff'))
            if plaintiff_table:
                parties['plaintiffs'] = self._parse_party_table(plaintiff_table, 'plaintiff')
            
            # Extract defendants
            defendant_table = soup.find('table', id=re.compile(r'.*gvDefendant'))
            if defendant_table:
                parties['defendants'] = self._parse_party_table(defendant_table, 'defendant')
                
        except Exception as e:
            logger.error(f"Error extracting parties info: {e}")
        
        return parties
    
    def _parse_party_table(self, table, party_type: str) -> List[Dict]:
        """Parse individual party table (plaintiff or defendant)"""
        parties = []
        
        try:
            rows = table.find_all('tr', class_='GridViewPlainRow')
            
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 3:
                    party_info = {}
                    
                    # Party name and address
                    party_cell = cells[0]
                    name_span = party_cell.find('span', id=re.compile(r'.*lblPartyName.*'))
                    address_span = party_cell.find('span', id=re.compile(r'.*lblPartyAddress.*'))
                    
                    party_info['name'] = name_span.get_text(strip=True) if name_span else ""
                    party_info['address'] = address_span.get_text(strip=True) if address_span else ""
                    
                    # Attorney name and address
                    attorney_cell = cells[2]
                    attorney_name_span = attorney_cell.find('span', id=re.compile(r'.*lblAttorneyName.*'))
                    attorney_address_span = attorney_cell.find('span', id=re.compile(r'.*lblAttorneyAddress.*'))
                    
                    party_info['attorney_name'] = attorney_name_span.get_text(strip=True) if attorney_name_span else ""
                    party_info['attorney_address'] = attorney_address_span.get_text(strip=True) if attorney_address_span else ""
                    party_info['party_type'] = party_type
                    
                    parties.append(party_info)
                    
        except Exception as e:
            logger.error(f"Error parsing {party_type} table: {e}")
        
        return parties
    
    def _extract_docket_entries(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract docket entries and motions"""
        docket_entries = []
        
        try:
            docket_table = soup.find('table', id=re.compile(r'.*gvDocketDetails'))
            if not docket_table:
                return docket_entries
            
            rows = docket_table.find_all('tr')
            
            for row in rows:
                if 'GridViewPlainRow' in row.get('class', []):
                    entry = self._parse_docket_row(row)
                    if entry:
                        docket_entries.append(entry)
                        
        except Exception as e:
            logger.error(f"Error extracting docket entries: {e}")
        
        return docket_entries
    
    def _parse_docket_row(self, row) -> Optional[Dict]:
        """Parse individual docket entry row"""
        try:
            cells = row.find_all('td')
            if len(cells) < 4:
                return None
            
            entry = {}
            
            # Date
            entry['date'] = cells[0].get_text(strip=True)
            
            # Filed by
            entry['filed_by'] = cells[1].get_text(strip=True)
            
            # Description
            entry['description'] = cells[2].get_text(strip=True)
            
            # Document link
            doc_cell = cells[3]
            doc_link = doc_cell.find('a', href=re.compile(r'DisplayImage\.asp'))
            
            if doc_link:
                entry['document_link'] = urljoin(self.base_url, doc_link['href'])
                entry['document_text'] = doc_link.get_text(strip=True)
                entry['has_document'] = True
                
                # Extract document ID from the link and clean it (remove spaces)
                match = re.search(r'gstrPDFOH=([^&]+)', doc_link['href'])
                if match:
                    raw_doc_id = match.group(1)
                    # Remove all spaces from document ID
                    entry['document_id'] = raw_doc_id.replace(' ', '')
                    # Also store the raw ID for reference
                    entry['raw_document_id'] = raw_doc_id
                else:
                    entry['document_id'] = ""
                    entry['raw_document_id'] = ""
            else:
                entry['document_link'] = ""
                entry['document_text'] = cells[3].get_text(strip=True)
                entry['has_document'] = False
                entry['document_id'] = ""
                entry['raw_document_id'] = ""
            
            return entry
            
        except Exception as e:
            logger.error(f"Error parsing docket row: {e}")
            return None
    
    def _extract_judges_magistrates(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract judges and magistrates information"""
        judges_magistrates = []
        
        try:
            judge_table = soup.find('table', id=re.compile(r'.*gvJudge'))
            if judge_table:
                rows = judge_table.find_all('tr')
                
                for row in rows:
                    if 'GridViewPlainRow' in row.get('class', []):
                        cells = row.find_all('td')
                        if len(cells) >= 2:
                            judge_info = {
                                'name': cells[0].get_text(strip=True),
                                'role': cells[1].get_text(strip=True) if len(cells) > 1 else "",
                                'date': cells[2].get_text(strip=True) if len(cells) > 2 else ""
                            }
                            judges_magistrates.append(judge_info)
                            
        except Exception as e:
            logger.error(f"Error extracting judges/magistrates: {e}")
        
        return judges_magistrates
    
    def _extract_service_records(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract service records"""
        service_records = []
        
        try:
            service_table = soup.find('table', id=re.compile(r'.*gvService'))
            if not service_table:
                return service_records
            
            rows = service_table.find_all('tr')
            
            for row in rows:
                if 'GridViewPlainRow' in row.get('class', []):
                    service_record = self._parse_service_row(row)
                    if service_record:
                        service_records.append(service_record)
                        
        except Exception as e:
            logger.error(f"Error extracting service records: {e}")
        
        return service_records
    
    def _parse_service_row(self, row) -> Optional[Dict]:
        """Parse individual service record row"""
        try:
            cells = row.find_all('td')
            if len(cells) < 6:
                return None
            
            service_record = {
                'party_name': cells[0].get_text(strip=True),
                'address': cells[1].get_text(strip=True),
                'issued_date': cells[2].get_text(strip=True),
                'served_date': cells[3].get_text(strip=True),
                'service_type': cells[4].get_text(strip=True),
                'method': cells[5].get_text(strip=True)
            }
            
            # Check for tracking links
            tracking_cell = cells[6] if len(cells) > 6 else None
            if tracking_cell:
                fedex_link = tracking_cell.find('a', href=re.compile(r'fedex'))
                usps_link = tracking_cell.find('a', href=re.compile(r'usps'))
                
                service_record['fedex_tracking'] = fedex_link['href'] if fedex_link else ""
                service_record['usps_tracking'] = usps_link['href'] if usps_link else ""
                service_record['tracking_number'] = tracking_cell.get_text(strip=True)
            
            # Check for document link
            doc_cell = cells[7] if len(cells) > 7 else None
            if doc_cell:
                doc_link = doc_cell.find('a', href=re.compile(r'DisplayImage\.asp'))
                if doc_link:
                    service_record['document_link'] = urljoin(self.base_url, doc_link['href'])
                    service_record['has_document'] = True
                else:
                    service_record['document_link'] = ""
                    service_record['has_document'] = False
            
            return service_record
            
        except Exception as e:
            logger.error(f"Error parsing service row: {e}")
            return None
    
    def _extract_all_documents(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract all document links from the page"""
        documents = []
        
        try:
            # Find all DisplayImage.asp links
            doc_links = soup.find_all('a', href=re.compile(r'DisplayImage\.asp'))
            
            for i, link in enumerate(doc_links):
                doc_info = {
                    'index': i + 1,
                    'link': urljoin(self.base_url, link['href']),
                    'text': link.get_text(strip=True),
                    'document_id': "",
                    'context': ""
                }
                
                # Extract document ID
                match = re.search(r'gstrPDFOH=([^&]+)', link['href'])
                if match:
                    raw_doc_id = match.group(1)
                    # Remove all spaces from document ID for clean filename
                    doc_info['document_id'] = raw_doc_id.replace(' ', '')
                    # Store raw ID for reference
                    doc_info['raw_document_id'] = raw_doc_id
                else:
                    doc_info['document_id'] = ""
                    doc_info['raw_document_id'] = ""
                
                # Get context (parent row information)
                parent_row = link.find_parent('tr')
                if parent_row:
                    doc_info['context'] = parent_row.get_text(strip=True)
                
                documents.append(doc_info)
                
        except Exception as e:
            logger.error(f"Error extracting documents: {e}")
        
        return documents
    
    def save_to_json(self, output_file: str) -> bool:
        """Save parsed data to JSON file"""
        try:
            with open(output_file, 'w', encoding='utf-8') as file:
                json.dump(self.case_data, file, indent=2, ensure_ascii=False)
            
            logger.info(f"Case data saved to {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving to JSON: {e}")
            return False
    
    def save_to_excel(self, output_file: str) -> bool:
        """Save parsed data to Excel file with multiple sheets"""
        try:
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # Basic info sheet
                basic_df = pd.DataFrame([self.case_data['basic_info']])
                basic_df.to_excel(writer, sheet_name='Basic_Info', index=False)
                
                # Parties sheet
                parties_data = []
                for plaintiff in self.case_data['parties']['plaintiffs']:
                    parties_data.append({**plaintiff, 'party_role': 'Plaintiff'})
                for defendant in self.case_data['parties']['defendants']:
                    parties_data.append({**defendant, 'party_role': 'Defendant'})
                
                if parties_data:
                    parties_df = pd.DataFrame(parties_data)
                    parties_df.to_excel(writer, sheet_name='Parties', index=False)
                
                # Docket entries sheet
                if self.case_data['docket_entries']:
                    docket_df = pd.DataFrame(self.case_data['docket_entries'])
                    docket_df.to_excel(writer, sheet_name='Docket_Entries', index=False)
                
                # Service records sheet
                if self.case_data['service_records']:
                    service_df = pd.DataFrame(self.case_data['service_records'])
                    service_df.to_excel(writer, sheet_name='Service_Records', index=False)
                
                # Documents sheet
                if self.case_data['documents']:
                    docs_df = pd.DataFrame(self.case_data['documents'])
                    docs_df.to_excel(writer, sheet_name='Documents', index=False)
            
            logger.info(f"Case data saved to Excel file: {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving to Excel: {e}")
            return False
    
    def get_document_download_urls(self) -> List[str]:
        """Get list of all document download URLs"""
        return [doc['link'] for doc in self.case_data.get('documents', [])]
    
    def print_summary(self):
        """Print a summary of the parsed case data"""
        if not self.case_data:
            print("No case data available")
            return
        
        print("="*60)
        print("CASE SUMMARY")
        print("="*60)
        
        basic = self.case_data.get('basic_info', {})
        print(f"Case Number: {basic.get('case_number', 'N/A')}")
        print(f"Case Caption: {basic.get('case_caption', 'N/A')}")
        print(f"Case Type: {basic.get('case_type', 'N/A')}")
        print(f"File Date: {basic.get('file_date', 'N/A')}")
        print(f"Judge: {basic.get('judge', 'N/A')}")
        
        print(f"\nPlaintiffs: {len(self.case_data.get('parties', {}).get('plaintiffs', []))}")
        print(f"Defendants: {len(self.case_data.get('parties', {}).get('defendants', []))}")
        print(f"Docket Entries: {len(self.case_data.get('docket_entries', []))}")
        print(f"Service Records: {len(self.case_data.get('service_records', []))}")
        print(f"Documents: {len(self.case_data.get('documents', []))}")
        
        print("\nDocument Links:")
        for doc in self.case_data.get('documents', [])[:5]:  # Show first 5
            print(f"  - {doc.get('text', 'N/A')}: {doc.get('link', 'N/A')}")
        
        if len(self.case_data.get('documents', [])) > 5:
            print(f"  ... and {len(self.case_data.get('documents', [])) - 5} more documents")


def main():
    """Main function to demonstrate the parser usage"""
    
    # Initialize parser
    parser = SummitCaseDetailsParser()
    
    # Parse the response_body.html file
    html_file = "response_body.html"
    
    try:
        print("Parsing Summit County case details HTML...")
        case_data = parser.parse_html_file(html_file)
        
        if case_data:
            # Print summary
            parser.print_summary()
            
            # Save to JSON
            json_file = f"case_details_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            parser.save_to_json(json_file)
            
            # Save to Excel
            excel_file = f"case_details_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            parser.save_to_excel(excel_file)
            
            # Get all document URLs
            doc_urls = parser.get_document_download_urls()
            print(f"\nFound {len(doc_urls)} document download URLs")
            
            # Save document URLs to text file
            urls_file = f"document_urls_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(urls_file, 'w') as f:
                for url in doc_urls:
                    f.write(f"{url}\n")
            
            print(f"Document URLs saved to: {urls_file}")
            
        else:
            print("Failed to parse case data")
    
    except Exception as e:
        print(f"Error in main: {e}")


if __name__ == "__main__":
    main()
