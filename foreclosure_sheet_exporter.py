#!/usr/bin/env python3
"""
Summit County Foreclosure Data to Google Sheets Exporter
Automatically collects case data and exports to Google Sheets with proper formatting.

Features:
- Scans all case folders for data
- Consolidates parsed PDF data, case details, and metadata
- Exports to Google Sheets with proper headers
- Handles incremental updates (new cases added to top)
- Extracts attorney website domains from emails
- Optimized for email automation workflows
- Runs continuously to monitor for new cases
"""

import json
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

# Google Sheets API
import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.service_account import Credentials as ServiceAccountCredentials

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sheet_exporter.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ForeclosureDataExporter:
    """Export foreclosure case data to Google Sheets"""
    
    def __init__(self, spreadsheet_url: str, check_interval_minutes: int = 30):
        self.spreadsheet_url = spreadsheet_url
        self.check_interval = check_interval_minutes * 60  # Convert to seconds
        self.data_folder = "Foreclosure_Cases_Data"
        self.processed_cases_file = "exported_cases.json"
        self.exported_cases = set()
        
        # Google Sheets setup
        self.gc = None
        self.worksheet = None
        
        # Load previously exported cases
        self.load_exported_cases()
        
        # Initialize Google Sheets connection
        self.setup_google_sheets()
    
    def setup_google_sheets(self):
        """Initialize Google Sheets API connection"""
        try:
            # If you have service account credentials
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # Option 1: Service Account (recommended for automation)
            try:
                creds = ServiceAccountCredentials.from_service_account_file(
                    'service_account.json', scope
                )
                self.gc = gspread.authorize(creds)
                logger.info("Connected to Google Sheets using service account")
            except FileNotFoundError:
                # Option 2: OAuth2 (for interactive use)
                logger.info("Service account not found, using OAuth2...")
                creds = None
                
                # Check for existing token
                if os.path.exists('token.json'):
                    creds = Credentials.from_authorized_user_file('token.json', scope)
                
                # If no valid credentials, get new ones
                if not creds or not creds.valid:
                    if creds and creds.expired and creds.refresh_token:
                        creds.refresh(Request())
                    else:
                        flow = InstalledAppFlow.from_client_secrets_file(
                            'credentials.json', scope
                        )
                        creds = flow.run_local_server(port=0)
                    
                    # Save credentials for next run
                    with open('token.json', 'w') as token:
                        token.write(creds.to_json())
                
                self.gc = gspread.authorize(creds)
                logger.info("Connected to Google Sheets using OAuth2")
            
            # Open the spreadsheet
            spreadsheet_id = self.extract_spreadsheet_id(self.spreadsheet_url)
            self.spreadsheet = self.gc.open_by_key(spreadsheet_id)
            self.worksheet = self.spreadsheet.sheet1  # Use first sheet
            
            logger.info(f"Connected to spreadsheet: {self.spreadsheet.title}")
            
        except Exception as e:
            logger.error(f"Error setting up Google Sheets: {e}")
            raise
    
    def extract_spreadsheet_id(self, url: str) -> str:
        """Extract spreadsheet ID from Google Sheets URL"""
        match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', url)
        if match:
            return match.group(1)
        else:
            raise ValueError(f"Cannot extract spreadsheet ID from URL: {url}")
    
    def load_exported_cases(self):
        """Load previously exported cases"""
        try:
            if os.path.exists(self.processed_cases_file):
                with open(self.processed_cases_file, 'r') as f:
                    data = json.load(f)
                    self.exported_cases = set(data.get('exported_cases', []))
                    logger.info(f"Loaded {len(self.exported_cases)} previously exported cases")
            else:
                self.exported_cases = set()
                logger.info("No previously exported cases found")
        except Exception as e:
            logger.error(f"Error loading exported cases: {e}")
            self.exported_cases = set()
    
    def save_exported_cases(self):
        """Save exported cases to file"""
        try:
            data = {
                'last_updated': datetime.now().isoformat(),
                'exported_cases': list(self.exported_cases)
            }
            with open(self.processed_cases_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved {len(self.exported_cases)} exported cases")
        except Exception as e:
            logger.error(f"Error saving exported cases: {e}")
    
    def scan_case_folders(self) -> List[Dict[str, Any]]:
        """Scan all case folders and collect data"""
        all_cases = []
        
        if not os.path.exists(self.data_folder):
            logger.warning(f"Data folder {self.data_folder} not found")
            return all_cases
        
        for case_folder in os.listdir(self.data_folder):
            case_path = os.path.join(self.data_folder, case_folder)
            
            if os.path.isdir(case_path):
                case_data = self.process_case_folder(case_path, case_folder)
                if case_data:
                    all_cases.append(case_data)
        
        # Sort by filing datetime (newest first)
        all_cases.sort(key=lambda x: x.get('filing_datetime', ''), reverse=True)
        
        logger.info(f"Collected data from {len(all_cases)} cases")
        return all_cases
    
    def process_case_folder(self, case_path: str, case_folder: str) -> Optional[Dict[str, Any]]:
        """Process a single case folder and extract all relevant data"""
        try:
            case_data = {'folder_name': case_folder}
            
            # Load parsed PDF data
            pdf_parsed_file = os.path.join(case_path, 'foreclosure_complaint_parsed.json')
            if os.path.exists(pdf_parsed_file):
                with open(pdf_parsed_file, 'r', encoding='utf-8') as f:
                    pdf_data = json.load(f)
                    case_data.update(pdf_data)
            
            # Load case details
            case_details_file = os.path.join(case_path, 'case_details.json')
            if os.path.exists(case_details_file):
                with open(case_details_file, 'r', encoding='utf-8') as f:
                    details_data = json.load(f)
                    case_data['case_details'] = details_data
            
            # Load metadata
            metadata_file = os.path.join(case_path, 'case_metadata.json')
            if os.path.exists(metadata_file):
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    case_data['metadata'] = metadata
            
            # Extract attorney website domain
            if 'attorney' in case_data and case_data['attorney'].get('email'):
                case_data['attorney_website'] = self.extract_website_domain(
                    case_data['attorney']['email']
                )
            
            # Format data for export
            formatted_data = self.format_case_for_export(case_data)
            return formatted_data
            
        except Exception as e:
            logger.error(f"Error processing case folder {case_folder}: {e}")
            return None
    
    def extract_website_domain(self, email: str) -> str:
        """Extract website domain from email address"""
        try:
            if '@' in email:
                domain = email.split('@')[1]
                return f"https://{domain}"
            return ""
        except Exception:
            return ""
    
    def format_case_for_export(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format case data for Google Sheets export"""
        formatted = {
            # Essential Case Information
            'case_number': case_data.get('case_number', ''),
            'filing_datetime': self.format_datetime(case_data.get('filing_datetime', '')),
            'filing_date': self.extract_date_only(case_data.get('filing_datetime', '')),
            'case_type': 'Foreclosure',
            'court': case_data.get('court', ''),
            'county': case_data.get('county', ''),
            
            # Parties Information
            'plaintiff': case_data.get('plaintiff', ''),
            'defendants': self.format_defendants(case_data.get('defendants', [])),
            'primary_defendant': self.get_primary_defendant(case_data.get('defendants', [])),
            
            # Property Information
            'property_address': case_data.get('property_address', ''),
            'parcel_number': case_data.get('parcel_number', ''),
            
            # Financial Information
            'redemption_price': self.format_currency(case_data.get('redemption_price', 0)),
            'redemption_good_through': case_data.get('redemption_good_through', ''),
            'lien_holder': case_data.get('lien_holder', ''),
            'tax_certificate_number': case_data.get('tax_certificate_number', ''),
            
            # Attorney Information
            'attorney_name': self.get_attorney_name(case_data.get('attorney', {})),
            'attorney_office': case_data.get('attorney', {}).get('office', ''),
            'attorney_email': case_data.get('attorney', {}).get('email', ''),
            'attorney_phone': case_data.get('attorney', {}).get('phone', ''),
            'attorney_website': case_data.get('attorney_website', ''),
            
            # Legal Information
            'statutes': self.format_list(case_data.get('statutes', [])),
            'relief_requested': self.format_list(case_data.get('relief_requested', [])),
            'exhibits': self.format_list(case_data.get('exhibits', [])),
            
            # Processing Information
            'processed_at': self.format_datetime(
                case_data.get('metadata', {}).get('processed_at', '')
            ),
            'pdf_file': case_data.get('file', ''),
            'has_pdf_data': bool(case_data.get('case_number')),
            'folder_name': case_data.get('folder_name', ''),
        }
        
        return formatted
    
    def format_datetime(self, dt_str: str) -> str:
        """Format datetime string for display"""
        if not dt_str:
            return ""
        try:
            if 'T' in dt_str:
                dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                return dt.strftime('%m/%d/%Y %H:%M:%S')
            return dt_str
        except Exception:
            return dt_str
    
    def extract_date_only(self, dt_str: str) -> str:
        """Extract date only from datetime string"""
        if not dt_str:
            return ""
        try:
            if 'T' in dt_str:
                dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                return dt.strftime('%m/%d/%Y')
            return dt_str.split(' ')[0] if ' ' in dt_str else dt_str
        except Exception:
            return dt_str
    
    def format_defendants(self, defendants: List[str]) -> str:
        """Format defendants list as comma-separated string"""
        if not defendants:
            return ""
        return ", ".join(defendants)
    
    def get_primary_defendant(self, defendants: List[str]) -> str:
        """Get primary (first) defendant"""
        if defendants:
            return defendants[0]
        return ""
    
    def format_currency(self, amount: Any) -> str:
        """Format currency amount"""
        if not amount:
            return ""
        try:
            return f"${float(amount):,.2f}"
        except (ValueError, TypeError):
            return str(amount)
    
    def get_attorney_name(self, attorney_data: Dict[str, Any]) -> str:
        """Get attorney name from attorney data"""
        if not attorney_data:
            return ""
        
        # Try different name fields
        name_fields = ['assistant_name', 'prosecutor_name', 'name']
        for field in name_fields:
            if attorney_data.get(field):
                return attorney_data[field]
        
        return ""
    
    def format_list(self, items: List[str]) -> str:
        """Format list as comma-separated string"""
        if not items:
            return ""
        return ", ".join(items)
    
    def setup_sheet_headers(self):
        """Setup Google Sheets headers"""
        headers = [
            'Case Number',
            'Filing Date',
            'Filing Time',
            'Case Type',
            'Court',
            'County',
            'Plaintiff',
            'Primary Defendant',
            'All Defendants',
            'Property Address',
            'Parcel Number',
            'Redemption Amount',
            'Redemption Good Through',
            'Lien Holder',
            'Tax Certificate #',
            'Attorney Name',
            'Attorney Office',
            'Attorney Email',
            'Attorney Phone',
            'Attorney Website',
            'Statutes',
            'Relief Requested',
            'Exhibits',
            'PDF File',
            'Processed At',
            'Folder Name'
        ]
        
        try:
            # Check if headers already exist
            existing_headers = self.worksheet.row_values(1)
            
            if not existing_headers or existing_headers != headers:
                # Clear and set headers
                self.worksheet.clear()
                self.worksheet.insert_row(headers, 1)
                
                # Format header row
                self.worksheet.format('1:1', {
                    'backgroundColor': {'red': 0.2, 'green': 0.6, 'blue': 1.0},
                    'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
                    'horizontalAlignment': 'CENTER'
                })
                
                logger.info("Sheet headers set up successfully")
            else:
                logger.info("Headers already exist and are correct")
                
        except Exception as e:
            logger.error(f"Error setting up headers: {e}")
            raise
    
    def export_cases_to_sheet(self, cases: List[Dict[str, Any]]):
        """Export cases to Google Sheets"""
        try:
            # Setup headers first
            self.setup_sheet_headers()
            
            # Get existing data to avoid duplicates
            existing_data = self.worksheet.get_all_records()
            existing_case_numbers = {row.get('Case Number', '') for row in existing_data}
            
            # Filter new cases
            new_cases = [
                case for case in cases 
                if case.get('case_number', '') not in existing_case_numbers
            ]
            
            if not new_cases:
                logger.info("No new cases to export")
                return
            
            logger.info(f"Exporting {len(new_cases)} new cases to Google Sheets")
            
            # Prepare data rows
            rows_to_insert = []
            for case in new_cases:
                row = [
                    case.get('case_number', ''),
                    case.get('filing_date', ''),
                    case.get('filing_datetime', ''),
                    case.get('case_type', ''),
                    case.get('court', ''),
                    case.get('county', ''),
                    case.get('plaintiff', ''),
                    case.get('primary_defendant', ''),
                    case.get('defendants', ''),
                    case.get('property_address', ''),
                    case.get('parcel_number', ''),
                    case.get('redemption_price', ''),
                    case.get('redemption_good_through', ''),
                    case.get('lien_holder', ''),
                    case.get('tax_certificate_number', ''),
                    case.get('attorney_name', ''),
                    case.get('attorney_office', ''),
                    case.get('attorney_email', ''),
                    case.get('attorney_phone', ''),
                    case.get('attorney_website', ''),
                    case.get('statutes', ''),
                    case.get('relief_requested', ''),
                    case.get('exhibits', ''),
                    case.get('pdf_file', ''),
                    case.get('processed_at', ''),
                    case.get('folder_name', '')
                ]
                rows_to_insert.append(row)
            
            # Insert new rows at the top (after headers)
            if rows_to_insert:
                # Insert rows starting from row 2 (after headers)
                self.worksheet.insert_rows(rows_to_insert, 2)
                
                # Apply formatting to new rows
                end_row = len(rows_to_insert) + 1
                self.worksheet.format(f'2:{end_row}', {
                    'horizontalAlignment': 'LEFT',
                    'wrapStrategy': 'WRAP',
                    'verticalAlignment': 'TOP'
                })
                
                logger.info(f"Successfully exported {len(new_cases)} cases to Google Sheets")
                
                # Update exported cases tracking
                for case in new_cases:
                    self.exported_cases.add(case.get('case_number', ''))
                
                self.save_exported_cases()
            
        except Exception as e:
            logger.error(f"Error exporting to Google Sheets: {e}")
            raise
    
    def run_continuous_export(self):
        """Run continuous export monitoring"""
        logger.info("Starting continuous foreclosure data export to Google Sheets...")
        logger.info(f"Spreadsheet URL: {self.spreadsheet_url}")
        logger.info(f"Check interval: {self.check_interval/60} minutes")
        
        try:
            while True:
                try:
                    logger.info("=" * 50)
                    logger.info("Starting export cycle...")
                    
                    # Scan for case data
                    cases = self.scan_case_folders()
                    
                    if cases:
                        # Export to Google Sheets
                        self.export_cases_to_sheet(cases)
                        
                        logger.info(f"Export cycle completed:")
                        logger.info(f"  Total cases found: {len(cases)}")
                        logger.info(f"  Total exported so far: {len(self.exported_cases)}")
                    else:
                        logger.info("No case data found")
                    
                    # Wait for next cycle
                    logger.info(f"Waiting {self.check_interval/60} minutes for next check...")
                    time.sleep(self.check_interval)
                    
                except Exception as e:
                    logger.error(f"Error in export cycle: {e}")
                    logger.info("Retrying in 5 minutes...")
                    time.sleep(300)  # Wait 5 minutes before retry
                    
        except KeyboardInterrupt:
            logger.info("Export monitoring stopped by user")
        except Exception as e:
            logger.error(f"Fatal error in continuous export: {e}")

def main():
    """Main function"""
    # Configuration
    SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1FIGskxOk1ctYaDluIfxkau_2j08ObMHNoLT9Wv4IwvE/edit?gid=0#gid=0"
    CHECK_INTERVAL_MINUTES = 30  # Check every 30 minutes
    
    try:
        logger.info("=" * 60)
        logger.info("SUMMIT COUNTY FORECLOSURE DATA EXPORTER STARTING")
        logger.info("=" * 60)
        
        # Initialize exporter
        exporter = ForeclosureDataExporter(
            spreadsheet_url=SPREADSHEET_URL,
            check_interval_minutes=CHECK_INTERVAL_MINUTES
        )
        
        # Run continuous export
        exporter.run_continuous_export()
        
    except KeyboardInterrupt:
        logger.info("\nData exporter stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        logger.info("Please check your Google Sheets credentials and permissions")
    
    finally:
        logger.info("Foreclosure data exporter ended")

if __name__ == "__main__":
    main()
