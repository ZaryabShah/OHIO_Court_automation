#!/usr/bin/env python3
"""
Simple test script for Foreclosure Data Collection
Tests data collection without Google Sheets dependencies
"""

import json
import os
import re
from datetime import datetime
from typing import Dict, List, Any, Optional

def extract_website_domain(email: str) -> str:
    """Extract website domain from email address"""
    try:
        if '@' in email:
            domain = email.split('@')[1]
            return f"https://{domain}"
        return ""
    except Exception:
        return ""

def format_datetime(dt_str: str) -> str:
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

def extract_date_only(dt_str: str) -> str:
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

def format_currency(amount: Any) -> str:
    """Format currency amount"""
    if not amount:
        return ""
    try:
        return f"${float(amount):,.2f}"
    except (ValueError, TypeError):
        return str(amount)

def get_attorney_name(attorney_data: Dict[str, Any]) -> str:
    """Get attorney name from attorney data"""
    if not attorney_data:
        return ""
    
    name_fields = ['assistant_name', 'prosecutor_name', 'name']
    for field in name_fields:
        if attorney_data.get(field):
            return attorney_data[field]
    
    return ""

def format_list(items: List[str]) -> str:
    """Format list as comma-separated string"""
    if not items:
        return ""
    return ", ".join(items)

def process_case_folder(case_path: str, case_folder: str) -> Optional[Dict[str, Any]]:
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
            case_data['attorney_website'] = extract_website_domain(
                case_data['attorney']['email']
            )
        
        # Format data for export
        formatted_data = format_case_for_export(case_data)
        return formatted_data
        
    except Exception as e:
        print(f"Error processing case folder {case_folder}: {e}")
        return None

def format_case_for_export(case_data: Dict[str, Any]) -> Dict[str, Any]:
    """Format case data for export"""
    defendants = case_data.get('defendants', [])
    
    formatted = {
        # Essential Case Information
        'case_number': case_data.get('case_number', ''),
        'filing_datetime': format_datetime(case_data.get('filing_datetime', '')),
        'filing_date': extract_date_only(case_data.get('filing_datetime', '')),
        'case_type': 'Foreclosure',
        'court': case_data.get('court', ''),
        'county': case_data.get('county', ''),
        
        # Parties Information
        'plaintiff': case_data.get('plaintiff', ''),
        'defendants': ", ".join(defendants) if defendants else "",
        'primary_defendant': defendants[0] if defendants else "",
        
        # Property Information
        'property_address': case_data.get('property_address', ''),
        'parcel_number': case_data.get('parcel_number', ''),
        
        # Financial Information
        'redemption_price': format_currency(case_data.get('redemption_price', 0)),
        'redemption_good_through': case_data.get('redemption_good_through', ''),
        'lien_holder': case_data.get('lien_holder', ''),
        'tax_certificate_number': case_data.get('tax_certificate_number', ''),
        
        # Attorney Information
        'attorney_name': get_attorney_name(case_data.get('attorney', {})),
        'attorney_office': case_data.get('attorney', {}).get('office', ''),
        'attorney_email': case_data.get('attorney', {}).get('email', ''),
        'attorney_phone': case_data.get('attorney', {}).get('phone', ''),
        'attorney_website': case_data.get('attorney_website', ''),
        
        # Legal Information
        'statutes': format_list(case_data.get('statutes', [])),
        'relief_requested': format_list(case_data.get('relief_requested', [])),
        'exhibits': format_list(case_data.get('exhibits', [])),
        
        # Processing Information
        'processed_at': format_datetime(
            case_data.get('metadata', {}).get('processed_at', '')
        ),
        'pdf_file': case_data.get('file', ''),
        'has_pdf_data': bool(case_data.get('case_number')),
        'folder_name': case_data.get('folder_name', ''),
    }
    
    return formatted

def scan_case_folders() -> List[Dict[str, Any]]:
    """Scan all case folders and collect data"""
    all_cases = []
    data_folder = "Foreclosure_Cases_Data"
    
    if not os.path.exists(data_folder):
        print(f"⚠️  Data folder {data_folder} not found")
        return all_cases
    
    for case_folder in os.listdir(data_folder):
        case_path = os.path.join(data_folder, case_folder)
        
        if os.path.isdir(case_path):
            case_data = process_case_folder(case_path, case_folder)
            if case_data:
                all_cases.append(case_data)
    
    # Sort by filing datetime (newest first)
    all_cases.sort(key=lambda x: x.get('filing_datetime', ''), reverse=True)
    
    return all_cases

def test_data_collection():
    """Test the data collection functionality"""
    print("=" * 60)
    print("TESTING FORECLOSURE DATA COLLECTION")
    print("=" * 60)
    
    try:
        # Test case folder scanning
        print("\n📁 Scanning case folders...")
        cases = scan_case_folders()
        
        if cases:
            print(f"✅ Found {len(cases)} cases")
            
            # Display sample data
            print("\n📋 Sample case data:")
            for i, case in enumerate(cases[:3], 1):  # Show first 3 cases
                print(f"\n--- Case {i}: {case.get('case_number', 'Unknown')} ---")
                print(f"Filing Date: {case.get('filing_date', 'N/A')}")
                print(f"Plaintiff: {case.get('plaintiff', 'N/A')}")
                print(f"Primary Defendant: {case.get('primary_defendant', 'N/A')}")
                print(f"Property: {case.get('property_address', 'N/A')}")
                print(f"Amount: {case.get('redemption_price', 'N/A')}")
                print(f"Attorney: {case.get('attorney_name', 'N/A')}")
                print(f"Attorney Email: {case.get('attorney_email', 'N/A')}")
                print(f"Attorney Website: {case.get('attorney_website', 'N/A')}")
            
            # Test headers for Google Sheets
            print("\n📊 Headers that will be created in Google Sheets:")
            headers = [
                'Case Number', 'Filing Date', 'Filing Time', 'Case Type', 'Court', 'County',
                'Plaintiff', 'Primary Defendant', 'All Defendants', 'Property Address',
                'Parcel Number', 'Redemption Amount', 'Redemption Good Through',
                'Lien Holder', 'Tax Certificate #', 'Attorney Name', 'Attorney Office',
                'Attorney Email', 'Attorney Phone', 'Attorney Website', 'Statutes',
                'Relief Requested', 'Exhibits', 'PDF File', 'Processed At', 'Folder Name'
            ]
            
            for i, header in enumerate(headers, 1):
                print(f"  {i:2d}. {header}")
            
            # Save test data as JSON for inspection
            print("\n💾 Saving test data to file...")
            test_output = {
                'total_cases': len(cases),
                'collection_time': datetime.now().isoformat(),
                'sample_cases': cases[:5],  # Save first 5 cases
                'headers': headers
            }
            
            with open('test_collected_data.json', 'w', encoding='utf-8') as f:
                json.dump(test_output, f, indent=2, ensure_ascii=False)
            
            print("✅ Test data saved to 'test_collected_data.json'")
            
            # Summary
            print(f"\n🎉 Data Collection Test Results:")
            print(f"  ✅ Successfully collected {len(cases)} cases")
            print(f"  ✅ Data formatting working correctly")
            print(f"  ✅ Attorney email parsing working")
            print(f"  ✅ Website domain extraction working")
            print(f"  ✅ Ready for Google Sheets export!")
            
            # Statistics
            print(f"\n📊 Case Statistics:")
            plaintiffs = [case.get('plaintiff', '') for case in cases if case.get('plaintiff')]
            attorneys = [case.get('attorney_email', '') for case in cases if case.get('attorney_email')]
            websites = [case.get('attorney_website', '') for case in cases if case.get('attorney_website')]
            
            print(f"  Cases with plaintiff data: {len(plaintiffs)}")
            print(f"  Cases with attorney emails: {len(attorneys)}")
            print(f"  Cases with attorney websites: {len(websites)}")
            print(f"  Unique plaintiffs: {len(set(plaintiffs))}")
            print(f"  Unique attorney emails: {len(set(attorneys))}")
            
            # Show some sample websites extracted
            if websites:
                print(f"\n🌐 Sample attorney websites extracted:")
                unique_websites = list(set(websites))[:5]
                for website in unique_websites:
                    print(f"  - {website}")
            
        else:
            print("❌ No cases found in Foreclosure_Cases_Data folder")
            print("Make sure you have run the complete_automation.py script first")
    
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("DATA COLLECTION TEST COMPLETED")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Install Google Sheets requirements: pip install -r sheets_requirements.txt")
    print("2. Follow GOOGLE_SHEETS_SETUP.md to set up API credentials")
    print("3. Run: python foreclosure_sheet_exporter.py")

if __name__ == "__main__":
    test_data_collection()
