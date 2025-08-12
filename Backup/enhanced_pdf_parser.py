#!/usr/bin/env python3
"""
Enhanced Foreclosure PDF Parser v3.0

Handles multiple foreclosure formats:
- Tax lien foreclosures (Summit County)
- Mortgage foreclosures (Private lenders)
- Different plaintiff/defendant formats
- Various property address formats
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

# Text extraction functions
def extract_text_pdfminer(path: str) -> str:
    try:
        from pdfminer.high_level import extract_text
        return extract_text(path) or ""
    except Exception:
        return ""

def extract_text_pypdf2(path: str) -> str:
    try:
        import PyPDF2
        text_parts = []
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text_parts.append(page.extract_text() or "")
        return "\n".join(text_parts)
    except Exception:
        return ""

def extract_text_any(path: str) -> str:
    """Try multiple text extraction methods"""
    text = extract_text_pdfminer(path)
    if not text.strip():
        text = extract_text_pypdf2(path)
    return text

# Utility functions
def clean_text(text: str) -> str:
    """Clean and normalize text"""
    if not text:
        return ""
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text.strip())
    # Remove extra punctuation
    text = re.sub(r'[,;]+$', '', text)
    return text

def parse_date_flexible(text: str) -> Optional[str]:
    """Parse dates in various formats"""
    if not text:
        return None
    
    # Common date patterns
    patterns = [
        r'(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2}:\d{2}:\d{2}\s*(?:AM|PM))',
        r'(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})',
        r'(\d{1,2}/\d{1,2}/\d{4})',
        r'(\w+\s+\d{1,2},\s*\d{4})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            try:
                if len(match.groups()) >= 2:
                    date_str = f"{match.group(1)} {match.group(2)}"
                else:
                    date_str = match.group(1)
                
                # Try to parse with various formats
                for fmt in ['%m/%d/%Y %I:%M:%S %p', '%m/%d/%Y', '%Y-%m-%dT%H:%M:%S', '%B %d, %Y']:
                    try:
                        dt = datetime.strptime(date_str, fmt)
                        return dt.isoformat()
                    except:
                        continue
            except:
                continue
    
    return None

@dataclass
class AttorneyInfo:
    prosecutor_name: Optional[str] = None
    office: Optional[str] = None
    assistant_name: Optional[str] = None
    bar_number: Optional[str] = None
    title: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None

@dataclass
class ForeclosureComplaint:
    file: str
    case_number: Optional[str] = None
    court: Optional[str] = None
    county: Optional[str] = None
    filing_datetime: Optional[str] = None
    plaintiff: Optional[str] = None
    defendants: List[str] = None
    property_address: Optional[str] = None
    parcel_number: Optional[str] = None
    lien_holder: Optional[str] = None
    tax_certificate_number: Optional[str] = None
    tax_certificate_sale_date: Optional[str] = None
    redemption_price: Optional[float] = None
    redemption_good_through: Optional[str] = None
    interest_rate_percent: Optional[float] = None
    statutes: List[str] = None
    relief_requested: List[str] = None
    exhibits: List[str] = None
    attorney: AttorneyInfo = None
    raw_excerpt: Optional[str] = None

    def __post_init__(self):
        if self.defendants is None:
            self.defendants = []
        if self.statutes is None:
            self.statutes = []
        if self.relief_requested is None:
            self.relief_requested = []
        if self.exhibits is None:
            self.exhibits = []
        if self.attorney is None:
            self.attorney = AttorneyInfo()

class EnhancedForeclosureParser:
    def __init__(self, text: str, filename: str):
        self.text = text
        self.filename = filename
        self.lines = [line.strip() for line in text.splitlines() if line.strip()]
    
    def parse(self) -> ForeclosureComplaint:
        """Parse the document and extract all relevant information"""
        result = ForeclosureComplaint(file=self.filename)
        
        # Extract basic info
        result.case_number = self.extract_case_number()
        result.court, result.county = self.extract_court_info()
        result.filing_datetime = self.extract_filing_datetime()
        
        # Extract parties
        result.plaintiff, result.defendants = self.extract_parties()
        
        # Extract property info
        result.property_address, result.parcel_number = self.extract_property_info()
        
        # Extract financial info
        result.lien_holder = self.extract_lien_holder()
        result.tax_certificate_number = self.extract_tax_certificate()
        result.tax_certificate_sale_date = self.extract_sale_date()
        result.redemption_price = self.extract_redemption_price()
        result.redemption_good_through = self.extract_redemption_period()
        result.interest_rate_percent = self.extract_interest_rate()
        
        # Extract legal info
        result.statutes = self.extract_statutes()
        result.relief_requested = self.extract_relief_requested()
        result.exhibits = self.extract_exhibits()
        
        # Extract attorney info
        result.attorney = self.extract_attorney_info()
        
        # Extract raw excerpt
        result.raw_excerpt = self.extract_raw_excerpt()
        
        return result
    
    def extract_case_number(self) -> Optional[str]:
        """Extract case number in various formats"""
        patterns = [
            r'CV[-\s]*(\d{4}[-\s]*\d{2}[-\s]*\d+)',
            r'Case\s+(?:No|Number)\.?\s*:?\s*CV[-\s]*(\d{4}[-\s]*\d{2}[-\s]*\d+)',
            r'^(CV[-\s]*\d{4}[-\s]*\d{2}[-\s]*\d+)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, self.text, re.I | re.M)
            for match in matches:
                case_num = match.group(1).replace(' ', '-').replace('--', '-')
                # Make sure it's not part of other text
                if not re.search(r'(?:JUDGE|COURT|PLAINTIFF|DEFENDANT)', case_num, re.I):
                    return f"CV-{case_num}" if not case_num.startswith('CV') else case_num
        
        return None
    
    def extract_court_info(self) -> tuple[Optional[str], Optional[str]]:
        """Extract court and county information"""
        court = None
        county = None
        
        # Look for standard court header
        patterns = [
            r'IN THE\s+(COURT OF [A-Z ]+)\s*\n\s*([A-Z]+)\s+COUNTY,\s*OHIO',
            r'(COURT OF COMMON PLEAS)\s*\n\s*([A-Z]+)\s+COUNTY,\s*OHIO',
            r'([A-Z]+)\s+COUNTY,\s*OHIO.*?COURT',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, self.text, re.I | re.S)
            if match:
                if 'COURT' in match.group(1).upper():
                    court = clean_text(match.group(1).title())
                    county = clean_text(match.group(2).title())
                else:
                    county = clean_text(match.group(1).title())
                    court = "Court of Common Pleas"
                break
        
        # Fallback
        if not court and re.search(r'COURT OF COMMON PLEAS', self.text, re.I):
            court = "Court of Common Pleas"
        
        if not county:
            county_match = re.search(r'([A-Z]+)\s+COUNTY,\s*OHIO', self.text, re.I)
            if county_match:
                county = clean_text(county_match.group(1).title())
        
        return court, county
    
    def extract_filing_datetime(self) -> Optional[str]:
        """Extract filing date and time"""
        # Look for date/time patterns in the document
        patterns = [
            r'(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2}:\d{2}:\d{2}\s*(?:AM|PM))',
            r'Filed.*?(\d{1,2}/\d{1,2}/\d{4})',
            r'(\w+\s+\d{1,2},\s*\d{4})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, self.text, re.I)
            if match:
                date_text = match.group(0)
                parsed_date = parse_date_flexible(date_text)
                if parsed_date:
                    return parsed_date
        
        return None
    
    def extract_parties(self) -> tuple[Optional[str], List[str]]:
        """Extract plaintiff and defendants"""
        plaintiff = None
        defendants = []
        
        # Extract plaintiff - handle different document formats
        # Order matters: check specific cases first, then general patterns
        
        # Format 1: RUSHMORE special case - company name before -vs- Plaintiff
        rushmore_pattern = re.search(r'(RUSHMORE\s+LOAN\s+MANAGEMENT\s+SERVICES\s+LLC)', self.text, re.I)
        if rushmore_pattern:
            plaintiff = "RUSHMORE LOAN MANAGEMENT SERVICES LLC"
            
            # For RUSHMORE case, defendants come after "-vs- Plaintiff," 
            vs_plaintiff_pattern = re.search(r'-vs-\s*Plaintiff,\s*(.*?)(?:\s*Defendants\.|\s*FIRST\s+COUNT)', self.text, re.I | re.S)
            if vs_plaintiff_pattern:
                defendant_text = vs_plaintiff_pattern.group(1).strip()
                
                # Split by "-AND-" to get individual defendants
                defendant_parts = re.split(r'\s*-AND-\s*', defendant_text)
                for part in defendant_parts:
                    lines = [line.strip() for line in part.split('\n') if line.strip()]
                    if lines:
                        # For each defendant section, take the first line as the name (before address)
                        first_line = lines[0]
                        if (first_line and 
                            not re.search(r'C/O|ALSO SERVE|^\d+\s|SUITE|FLOOR|WASHINGTON|CLEVELAND|COLUMBUS', first_line, re.I) and
                            len(first_line) > 2 and len(first_line) < 80):
                            # Clean up address info from name
                            name_only = re.split(r'\s+\d+\s+', first_line)[0]  # Remove address starting with number
                            name_only = re.sub(r'\s+(AKRON|CLEVELAND|COLUMBUS|WASHINGTON).*$', '', name_only, flags=re.I)
                            name_only = name_only.strip()
                            
                            if name_only and len(name_only) > 2:
                                defendants.append(name_only)
        
        # Format 2: Tax lien format - KRISTEN M. SCALISE (only if not RUSHMORE)
        elif re.search(r'(KRISTEN\s+M\.\s+SCALISE)', self.text, re.I):
            plaintiff = "KRISTEN M. SCALISE"
            
            # For tax lien, extract defendants after "vs."
            vs_pattern = re.search(r'vs\.\s*(.*?)\s*(?:Defendant\(s\)|$)', self.text, re.I | re.S)
            if vs_pattern:
                defendant_text = vs_pattern.group(1)
                lines = defendant_text.split('\n')
                
                for line in lines:
                    line = clean_text(line)
                    if (line and 
                        len(line) > 3 and len(line) < 100 and
                        not re.search(r'\d{4,5}|\b(?:STREET|ST|AVENUE|AVE|ROAD|RD|DRIVE|DR|LANE|LN|COURT|CT)\b', line, re.I) and
                        not re.search(r'\b(?:OHIO|OH)\s*\d{5}', line, re.I) and
                        not re.search(r'CASE|NUMBER|JUDGE|COMPLAINT|FORC|PAGE', line, re.I) and
                        len(line.split()) >= 2 and len(line.split()) <= 8):
                        
                        # Check if it's a reasonable name format
                        if re.match(r'^[A-Z][A-Za-z\s.,&\'-]+(?:,\s*[A-Z]{2,})?$', line):
                            defendants.append(line)
        
        # Format 3: Regular mortgage foreclosure format
        else:
            # Look for plaintiff company before "Plaintiff" keyword
            plaintiff_section = re.search(r'SUMMIT\s+COUNTY,\s+OHIO\s*(.*?)\s*CASE\s+NO', self.text, re.I | re.S)
            if plaintiff_section:
                company_text = plaintiff_section.group(1).strip()
                lines = [line.strip() for line in company_text.split('\n') if line.strip()]
                
                # Filter out unwanted lines and build company name
                company_parts = []
                for line in lines:
                    if (line and 
                        not line.startswith('c/o') and 
                        not re.match(r'^\d+\s+', line) and
                        not re.search(r'Ste\s+\d+|Suite\s+\d+|Floor|Avenue|Street|Pkwy', line, re.I)):
                        company_parts.append(line)
                
                if company_parts:
                    plaintiff = ' '.join(company_parts[:3])  # Take first 3 lines
                    plaintiff = re.sub(r'\s+', ' ', plaintiff).strip()
            
            # For regular mortgage foreclosure, extract defendants after "-vs-"
            vs_pattern = re.search(r'-vs-\s*(.*?)(?:\s*Defendants|\s*FIRST\s+COUNT)', self.text, re.I | re.S)
            if vs_pattern:
                defendant_text = vs_pattern.group(1).strip()
                
                # Split by "-and-" to get individual defendants
                defendant_parts = re.split(r'\s*-and-\s*', defendant_text)
                for part in defendant_parts:
                    lines = part.split('\n')
                    if lines:
                        # Take the first line as the defendant name
                        defendant_name = lines[0].strip()
                        if (defendant_name and 
                            not re.match(r'^\d+\s+', defendant_name) and
                            len(defendant_name) > 3):
                            defendants.append(defendant_name)
        
        return plaintiff, defendants
    
    def extract_property_info(self) -> tuple[Optional[str], Optional[str]]:
        """Extract property address and parcel number"""
        address = None
        parcel = None
        
        # Property address patterns - multiple approaches
        address_patterns = [
            # Explicit property address labels
            r'PROPERTY\s+ADDRESS\s*:?\s*([^\n]+(?:\n[^\n]*OH\s*\d{5})?)',
            r'Property\s+Address\s*:?\s*([^\n]+(?:\n[^\n]*OH\s*\d{5})?)',
            r'Property\s+Description\s*:?\s*([^\n]+(?:\n[^\n]*OH\s*\d{5})?)',
            # Address patterns in the text
            r'(\d{1,6}\s+[A-Za-z0-9 .\'-]+[,\s]+[A-Za-z .\'-]+[,\s]+OH\s*\d{5})',
            r'(\d{1,6}\s+[A-Z][A-Z\s]+(?:STREET|ST|AVENUE|AVE|ROAD|RD|DRIVE|DR|LANE|LN|COURT|CT)[^\n]*OH\s*\d{5})',
        ]
        
        for pattern in address_patterns:
            match = re.search(pattern, self.text, re.I | re.S)
            if match:
                address = clean_text(re.sub(r'\s+', ' ', match.group(1)))
                # Clean up any duplicate text
                address = re.sub(r'Property Address:\s*', '', address, flags=re.I)
                if len(address) > 10:  # Reasonable address length
                    break
        
        # Parcel number patterns - multiple formats
        parcel_patterns = [
            r'(?:Permanent\s+)?Parcel\s+(?:Number|No\.?)\s*:?\s*([A-Za-z0-9\-]+)',
            r'PPN[#:\s]*([A-Za-z0-9\-\s]+)',
            r'Parcel\s*ID\s*:?\s*([A-Za-z0-9\-]+)',
            r'Tax\s+ID\s*:?\s*([A-Za-z0-9\-]+)',
        ]
        
        for pattern in parcel_patterns:
            match = re.search(pattern, self.text, re.I)
            if match:
                parcel_candidate = clean_text(match.group(1))
                # Clean up PPN format (may have spaces or extra text)
                parcel_candidate = re.sub(r'\s+AND\s+.*$', '', parcel_candidate, flags=re.I)
                parcel_candidate = re.sub(r'\s+', '', parcel_candidate)
                if len(parcel_candidate) > 2 and len(parcel_candidate) < 20:
                    parcel = parcel_candidate
                    break
        
        return address, parcel
    
    def extract_lien_holder(self) -> Optional[str]:
        """Extract lien holder information"""
        patterns = [
            r'lien\s+(?:vested\s+in|held\s+by)\s+([A-Za-z0-9 .,&\-]+?)(?:[,.]|$)',
            r'To\s+foreclose\s+the\s+lien\s+vested\s+in\s+([^\n]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, self.text, re.I)
            if match:
                return clean_text(match.group(1))
        
        return None
    
    def extract_tax_certificate(self) -> Optional[str]:
        """Extract tax certificate number"""
        patterns = [
            r'Tax\s+Certificate\s+(?:Number|No\.?)\s*:?\s*([A-Za-z0-9\-]+)',
            r'Certificate\s+Number\(?s?\)?\s*:?\s*([A-Za-z0-9\-]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, self.text, re.I)
            if match:
                return clean_text(match.group(1))
        
        return None
    
    def extract_sale_date(self) -> Optional[str]:
        """Extract tax certificate sale date"""
        patterns = [
            r'(?:Tax\s+)?Sale\s+Date\s*:?\s*([A-Za-z0-9\s,/-]+)',
            r'(\d{4}-\d{2}-\d{2})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, self.text, re.I)
            if match:
                return parse_date_flexible(match.group(1))
        
        return None
    
    def extract_redemption_price(self) -> Optional[float]:
        """Extract redemption price"""
        patterns = [
            r'Redemption\s+Price\s*:?\s*\$?([0-9,]+\.?\d*)',
            r'\$([0-9,]+\.?\d*)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, self.text, re.I)
            if match:
                try:
                    return float(match.group(1).replace(',', ''))
                except:
                    continue
        
        return None
    
    def extract_redemption_period(self) -> Optional[str]:
        """Extract redemption good through period"""
        patterns = [
            r'Redemption\s+good\s+through\s*:?\s*([A-Za-z0-9\s-]+)',
            r'good\s+through\s*:?\s*([A-Za-z0-9\s-]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, self.text, re.I)
            if match:
                return clean_text(match.group(1))
        
        return None
    
    def extract_interest_rate(self) -> Optional[float]:
        """Extract interest rate"""
        patterns = [
            r'(?:interest\s+rate|rate)\s*:?\s*([0-9.]+)%?',
            r'([0-9.]+)%\s*(?:interest|rate)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, self.text, re.I)
            if match:
                try:
                    return float(match.group(1))
                except:
                    continue
        
        return None
    
    def extract_statutes(self) -> List[str]:
        """Extract Ohio Revised Code statutes"""
        statutes = []
        patterns = [
            r'R\.C\.?\s*([0-9]+\.[0-9]+)',
            r'(?:Ohio\s+)?Revised\s+Code\s+(?:Section\s+)?([0-9]+\.[0-9]+)',
            r'Section\s+([0-9]+\.[0-9]+)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, self.text, re.I)
            for match in matches:
                statute = f"R.C.{match.group(1)}"
                if statute not in statutes:
                    statutes.append(statute)
        
        return sorted(statutes)
    
    def extract_relief_requested(self) -> List[str]:
        """Extract relief requested"""
        relief = []
        
        if re.search(r'foreclos', self.text, re.I):
            relief.append("Foreclosure of liens")
        
        if re.search(r'sheriff.*?sale', self.text, re.I):
            relief.append("Order sheriff's sale")
        
        return relief
    
    def extract_exhibits(self) -> List[str]:
        """Extract exhibit references"""
        exhibits = []
        patterns = [
            r'Exhibit\s+([A-Z])',
            r'EXHIBIT\s+([A-Z])',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, self.text)
            for match in matches:
                exhibit = match.group(1)
                if exhibit not in exhibits:
                    exhibits.append(exhibit)
        
        return sorted(exhibits)
    
    def extract_attorney_info(self) -> AttorneyInfo:
        """Extract attorney information"""
        attorney = AttorneyInfo()
        
        # Look for specific attorney patterns
        attorney_name_patterns = [
            r'(?:Assistant\s+Prosecuting\s+Attorney|Attorney\s+for\s+Plaintiff)\s*:?\s*([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+),?\s*Esq\.?',
            r'Una\s+Lakic',  # Specific to Summit County cases
            r'F\.\s+Peter\s+Costello',  # Another common attorney
        ]
        
        for pattern in attorney_name_patterns:
            match = re.search(pattern, self.text, re.I)
            if match:
                attorney.assistant_name = clean_text(match.group(1) if match.lastindex else match.group(0))
                break
        
        # Prosecutor office
        prosecutor_patterns = [
            r'(ELLIOT\s+KOLKOVICH)',
            r'Summit\s+County\s+Prosecutor',
        ]
        
        for pattern in prosecutor_patterns:
            match = re.search(pattern, self.text, re.I)
            if match:
                if 'KOLKOVICH' in match.group(0):
                    attorney.prosecutor_name = 'ELLIOT KOLKOVICH'
                    attorney.office = 'Summit County Prosecutor'
                elif 'Prosecutor' in match.group(0):
                    attorney.office = 'Summit County Prosecutor'
                break
        
        # Bar number
        bar_patterns = [
            r'(?:Bar\s+(?:No|Number)|Registration\s+No\.?)\s*:?\s*(\d+)',
            r'(\d{7})',  # 7-digit bar numbers
        ]
        
        for pattern in bar_patterns:
            match = re.search(pattern, self.text, re.I)
            if match:
                bar_num = match.group(1)
                if len(bar_num) == 7:  # Valid Ohio bar number format
                    attorney.bar_number = bar_num
                    break
        
        # Phone number
        phone_match = re.search(r'\((\d{3})\)\s*(\d{3})-(\d{4})', self.text)
        if phone_match:
            attorney.phone = f"({phone_match.group(1)}) {phone_match.group(2)}-{phone_match.group(3)}"
        
        # Email
        email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', self.text)
        if email_match:
            attorney.email = email_match.group(1)
        
        # Address
        address_patterns = [
            r'(\d+\s+University\s+Avenue[^\n]*)',
            r'(\d+[^\n]*(?:Avenue|Street|Road|Drive|Lane|Court)[^\n]*)',
        ]
        
        for pattern in address_patterns:
            match = re.search(pattern, self.text, re.I)
            if match:
                attorney.address = clean_text(match.group(1))
                break
        
        # Title
        if attorney.assistant_name and 'Summit County' in (attorney.office or ''):
            attorney.title = 'Assistant Prosecuting Attorney'
        
        return attorney
    
    def extract_raw_excerpt(self) -> str:
        """Extract first 500 characters as raw excerpt"""
        # Clean text and take first 500 chars
        clean = re.sub(r'\s+', ' ', self.text[:1000]).strip()
        return clean[:500] + "..." if len(clean) > 500 else clean

def parse_pdf(file_path: str) -> Dict[str, Any]:
    """Parse a single PDF file"""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Extract text
    text = extract_text_any(str(path))
    if not text.strip():
        raise ValueError(f"Could not extract text from: {file_path}")
    
    # Parse the document
    parser = EnhancedForeclosureParser(text, path.name)
    result = parser.parse()
    
    return asdict(result)

def main():
    parser = argparse.ArgumentParser(description="Enhanced Foreclosure PDF Parser")
    parser.add_argument("files", nargs="+", help="PDF files to parse")
    parser.add_argument("--output", "-o", help="Output JSON file")
    
    args = parser.parse_args()
    
    results = []
    for file_path in args.files:
        try:
            result = parse_pdf(file_path)
            results.append(result)
        except Exception as e:
            print(f"Error parsing {file_path}: {e}", file=sys.stderr)
            continue
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
    else:
        print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
