"""
Summit County Court Records HTML Parser
Parses the HTML results from Summit County court records searches to extract structured data.
"""

import re
import json
import csv
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin, parse_qs, urlparse
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional


@dataclass
class CourtCase:
    """Data class representing a court case record"""
    filing_date: str
    case_number: str
    case_caption: str
    case_detail_url: str
    case_type: str = "Foreclosure"
    division: str = "Civil"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)


class SummitCountyParser:
    """Parser for Summit County court records HTML"""
    
    def __init__(self, base_url: str = "https://clerkweb.summitoh.net/PublicSite/"):
        """
        Initialize the parser
        
        Args:
            base_url (str): Base URL for constructing full URLs
        """
        self.base_url = base_url
        self.search_metadata = {}
        
    def parse_html_file(self, file_path: str) -> List[CourtCase]:
        """
        Parse an HTML file and extract court case data
        
        Args:
            file_path (str): Path to the HTML file
            
        Returns:
            List[CourtCase]: List of parsed court cases
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                html_content = file.read()
            
            return self.parse_html_content(html_content)
            
        except Exception as e:
            print(f"Error reading HTML file: {e}")
            return []
    
    def parse_html_content(self, html_content: str) -> List[CourtCase]:
        """
        Parse HTML content and extract court case data
        
        Args:
            html_content (str): Raw HTML content
            
        Returns:
            List[CourtCase]: List of parsed court cases
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract search metadata
            self._extract_search_metadata(soup)
            
            # Extract case data from the results table
            cases = self._extract_cases_from_table(soup)
            
            print(f"Successfully parsed {len(cases)} court cases")
            return cases
            
        except Exception as e:
            print(f"Error parsing HTML content: {e}")
            return []
    
    def _extract_search_metadata(self, soup: BeautifulSoup) -> None:
        """Extract metadata about the search (date, case type, division, etc.)"""
        try:
            # Extract division (Civil, Criminal, etc.)
            division_elem = soup.find('span', id='ContentPlaceHolder1_lblDivision')
            if division_elem:
                self.search_metadata['division'] = division_elem.get_text(strip=True)
            
            # Extract search criteria (Date and Case Type)
            selection_elem = soup.find('span', id='ContentPlaceHolder1_lblSelection')
            if selection_elem:
                selection_text = selection_elem.get_text(strip=True)
                self.search_metadata['search_criteria'] = selection_text
                
                # Parse date and case type from the selection text
                # Format: "Date: 08/08/2024 Case Type: Foreclosure"
                date_match = re.search(r'Date:\s*(\d{2}/\d{2}/\d{4})', selection_text)
                if date_match:
                    self.search_metadata['search_date'] = date_match.group(1)
                
                case_type_match = re.search(r'Case Type:\s*([^\\s]+)', selection_text)
                if case_type_match:
                    self.search_metadata['case_type'] = case_type_match.group(1)
            
            # Extract results count
            status_elem = soup.find('span', id='ContentPlaceHolder1_lblStatus')
            if status_elem:
                status_text = status_elem.get_text(strip=True)
                self.search_metadata['results_summary'] = status_text
                
                # Parse total count
                # Format: "Showing Results From 1-7 of 7"
                count_match = re.search(r'of\s+(\d+)', status_text)
                if count_match:
                    self.search_metadata['total_results'] = int(count_match.group(1))
            
            # Extract page title
            title_elem = soup.find('title')
            if title_elem:
                self.search_metadata['page_title'] = title_elem.get_text(strip=True)
                
        except Exception as e:
            print(f"Error extracting search metadata: {e}")
    
    def _extract_cases_from_table(self, soup: BeautifulSoup) -> List[CourtCase]:
        """Extract case data from the results table"""
        cases = []
        
        try:
            # Find the main results table
            results_table = soup.find('table', id='ContentPlaceHolder1_gvMixedResults')
            
            if not results_table:
                print("Results table not found")
                return cases
            
            # Find all data rows (skip header row)
            rows = results_table.find('tbody').find_all('tr')[1:]  # Skip header row
            
            for row in rows:
                try:
                    cells = row.find_all('td')
                    
                    if len(cells) >= 3:
                        # Extract filing date
                        filing_date = cells[0].get_text(strip=True)
                        
                        # Extract case number and URL
                        case_link = cells[1].find('a')
                        if case_link:
                            case_number = case_link.get_text(strip=True)
                            case_detail_url = case_link.get('href', '')
                            
                            # Convert relative URL to absolute URL
                            if case_detail_url and not case_detail_url.startswith('http'):
                                case_detail_url = urljoin(self.base_url, case_detail_url)
                        else:
                            case_number = cells[1].get_text(strip=True)
                            case_detail_url = ""
                        
                        # Extract case caption
                        case_caption = cells[2].get_text(strip=True)
                        
                        # Create CourtCase object
                        court_case = CourtCase(
                            filing_date=filing_date,
                            case_number=case_number,
                            case_caption=case_caption,
                            case_detail_url=case_detail_url,
                            case_type=self.search_metadata.get('case_type', 'Foreclosure'),
                            division=self.search_metadata.get('division', 'Civil')
                        )
                        
                        cases.append(court_case)
                        
                except Exception as e:
                    print(f"Error parsing row: {e}")
                    continue
            
        except Exception as e:
            print(f"Error extracting cases from table: {e}")
        
        return cases
    
    def get_search_metadata(self) -> Dict:
        """Get the extracted search metadata"""
        return self.search_metadata.copy()
    
    def save_cases_to_json(self, cases: List[CourtCase], filename: str) -> bool:
        """
        Save cases to a JSON file
        
        Args:
            cases (List[CourtCase]): List of court cases
            filename (str): Output filename
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Prepare data for JSON export
            export_data = {
                'metadata': self.search_metadata,
                'extracted_at': datetime.now().isoformat(),
                'total_cases': len(cases),
                'cases': [case.to_dict() for case in cases]
            }
            
            with open(filename, 'w', encoding='utf-8') as file:
                json.dump(export_data, file, indent=2, ensure_ascii=False)
            
            print(f"Cases saved to JSON file: {filename}")
            return True
            
        except Exception as e:
            print(f"Error saving to JSON: {e}")
            return False
    
    def save_cases_to_csv(self, cases: List[CourtCase], filename: str) -> bool:
        """
        Save cases to a CSV file
        
        Args:
            cases (List[CourtCase]): List of court cases
            filename (str): Output filename
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not cases:
                print("No cases to save")
                return False
            
            fieldnames = ['filing_date', 'case_number', 'case_caption', 'case_detail_url', 'case_type', 'division']
            
            with open(filename, 'w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                
                for case in cases:
                    writer.writerow(case.to_dict())
            
            print(f"Cases saved to CSV file: {filename}")
            return True
            
        except Exception as e:
            print(f"Error saving to CSV: {e}")
            return False
    
    def print_cases_summary(self, cases: List[CourtCase]) -> None:
        """Print a summary of the parsed cases"""
        print("\n" + "="*80)
        print("SUMMIT COUNTY COURT RECORDS SUMMARY")
        print("="*80)
        
        # Print metadata
        if self.search_metadata:
            print("\nSEARCH INFORMATION:")
            for key, value in self.search_metadata.items():
                print(f"  {key.replace('_', ' ').title()}: {value}")
        
        print(f"\nTOTAL CASES FOUND: {len(cases)}")
        
        if cases:
            print("\nCASE DETAILS:")
            print("-" * 80)
            
            for i, case in enumerate(cases, 1):
                print(f"\n{i}. Case Number: {case.case_number}")
                print(f"   Filing Date: {case.filing_date}")
                print(f"   Caption: {case.case_caption}")
                print(f"   Detail URL: {case.case_detail_url}")
                print(f"   Type: {case.case_type}")
                print(f"   Division: {case.division}")
        
        print("\n" + "="*80)
    
    def extract_case_numbers(self, cases: List[CourtCase]) -> List[str]:
        """Extract just the case numbers as a list"""
        return [case.case_number for case in cases]
    
    def filter_cases_by_date(self, cases: List[CourtCase], start_date: str, end_date: str = None) -> List[CourtCase]:
        """
        Filter cases by filing date
        
        Args:
            cases (List[CourtCase]): List of cases to filter
            start_date (str): Start date in MM/DD/YYYY format
            end_date (str): End date in MM/DD/YYYY format (optional)
            
        Returns:
            List[CourtCase]: Filtered cases
        """
        try:
            start_dt = datetime.strptime(start_date, '%m/%d/%Y')
            end_dt = datetime.strptime(end_date, '%m/%d/%Y') if end_date else start_dt
            
            filtered_cases = []
            for case in cases:
                try:
                    case_dt = datetime.strptime(case.filing_date, '%m/%d/%Y')
                    if start_dt <= case_dt <= end_dt:
                        filtered_cases.append(case)
                except ValueError:
                    print(f"Invalid date format for case {case.case_number}: {case.filing_date}")
                    continue
            
            return filtered_cases
            
        except ValueError as e:
            print(f"Invalid date format: {e}")
            return cases
    
    def search_cases_by_caption(self, cases: List[CourtCase], search_term: str) -> List[CourtCase]:
        """
        Search cases by caption text
        
        Args:
            cases (List[CourtCase]): List of cases to search
            search_term (str): Search term
            
        Returns:
            List[CourtCase]: Matching cases
        """
        search_term = search_term.lower()
        return [case for case in cases if search_term in case.case_caption.lower()]


def main():
    """Example usage of the parser"""
    
    # Initialize parser
    parser = SummitCountyParser()
    
    # Example HTML file path (adjust as needed)
    html_file = "results/summit_county_results_20250809_202335.html"
    
    try:
        # Parse the HTML file
        print(f"Parsing HTML file: {html_file}")
        cases = parser.parse_html_file(html_file)
        
        if not cases:
            print("No cases found or error occurred during parsing")
            return
        
        # Print summary
        parser.print_cases_summary(cases)
        
        # Save to different formats
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save to JSON
        json_filename = f"results/parsed_cases_{timestamp}.json"
        parser.save_cases_to_json(cases, json_filename)
        
        # Save to CSV
        csv_filename = f"results/parsed_cases_{timestamp}.csv"
        parser.save_cases_to_csv(cases, csv_filename)
        
        # Example filtering
        print("\n" + "="*80)
        print("EXAMPLE FILTERING:")
        print("="*80)
        
        # Filter by specific search terms
        search_results = parser.search_cases_by_caption(cases, "KRISTEN")
        print(f"\nCases mentioning 'KRISTEN': {len(search_results)}")
        for case in search_results:
            print(f"  - {case.case_number}: {case.case_caption}")
        
        # Extract just case numbers
        case_numbers = parser.extract_case_numbers(cases)
        print(f"\nAll Case Numbers: {case_numbers}")
        
    except Exception as e:
        print(f"Error in main: {e}")


if __name__ == "__main__":
    main()
