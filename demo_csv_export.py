#!/usr/bin/env python3
"""
Demo script showing Google Sheets export format
Creates a CSV file showing exactly what would be exported to Google Sheets
"""

import csv
import json
import os
from datetime import datetime

def create_demo_csv():
    """Create a demo CSV showing the Google Sheets format"""
    
    print("=" * 60)
    print("GOOGLE SHEETS EXPORT DEMO")
    print("=" * 60)
    
    # Load the test data we created earlier
    if not os.path.exists('test_collected_data.json'):
        print("❌ Please run test_data_collection_simple.py first")
        return
    
    with open('test_collected_data.json', 'r', encoding='utf-8') as f:
        test_data = json.load(f)
    
    cases = test_data['sample_cases']
    headers = test_data['headers']
    
    # Create CSV filename
    csv_filename = f"foreclosure_data_demo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    print(f"\n📄 Creating demo CSV: {csv_filename}")
    print(f"📊 Headers: {len(headers)} columns")
    print(f"🗂️  Data: {len(cases)} cases")
    
    # Create CSV
    with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        # Write headers
        writer.writerow(headers)
        
        # Write data rows
        for case in cases:
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
            writer.writerow(row)
    
    print(f"✅ Demo CSV created successfully!")
    
    # Show sample data
    print(f"\n📋 Sample exported data:")
    print(f"{'Case Number':<20} {'Plaintiff':<30} {'Attorney Website':<25}")
    print("-" * 75)
    
    for case in cases[:5]:
        case_num = (case.get('case_number') or 'N/A')[:19]
        plaintiff = (case.get('plaintiff') or 'N/A')[:29]
        website = (case.get('attorney_website') or 'N/A')[:24]
        print(f"{case_num:<20} {plaintiff:<30} {website:<25}")
    
    # Show attorney websites extracted
    print(f"\n🌐 Attorney Websites Extracted:")
    websites = []
    for case in cases:
        email = case.get('attorney_email', '')
        website = case.get('attorney_website', '')
        if email and website:
            websites.append(f"  {email:<35} → {website}")
    
    for website in websites[:8]:  # Show first 8
        print(website)
    
    print(f"\n📧 Ready for Email Automation:")
    print(f"  ✅ Attorney emails extracted")
    print(f"  ✅ Attorney websites identified") 
    print(f"  ✅ Contact information organized")
    print(f"  ✅ Case details properly formatted")
    
    print(f"\n🎯 Next Steps:")
    print(f"  1. Set up Google Sheets API credentials (see GOOGLE_SHEETS_SETUP.md)")
    print(f"  2. Run: python foreclosure_sheet_exporter.py")
    print(f"  3. Data will be automatically exported to your Google Sheets")
    print(f"  4. Use the spreadsheet for your email automation workflow")
    
    print(f"\n📊 This CSV shows exactly what will appear in Google Sheets!")
    print(f"   File: {csv_filename}")
    
    return csv_filename

if __name__ == "__main__":
    create_demo_csv()
