#!/usr/bin/env python3

import json
import requests
from urllib.parse import urlparse, parse_qs, urljoin

def convert_display_image_to_pdf_url(display_image_url: str) -> str:
    """Convert DisplayImage.asp URL to direct PDF URL"""
    try:
        parsed_url = urlparse(display_image_url)
        query_params = parse_qs(parsed_url.query)
        
        if 'gstrPDFOH' in query_params:
            pdf_id = query_params['gstrPDFOH'][0].strip()
            clean_pdf_id = pdf_id.replace(' ', '')
            base_url = "https://clerkweb.summitoh.net/PublicSite/"
            pdf_url = urljoin(base_url, f"Documents/{clean_pdf_id}.pdf")
            return pdf_url
        
        return display_image_url
        
    except Exception as e:
        print(f"Error converting URL: {e}")
        return display_image_url

def test_urls():
    # Test cases that failed vs the one that worked
    test_cases = [
        {
            "case": "CV-2025-08-3686 (FAILED)",
            "display_url": "https://clerkweb.summitoh.net/PublicSite/DisplayImage.asp?gstrPDFOH=vola00000046        00001EA1",
            "expected_id": "vola0000004600001EA1"
        },
        {
            "case": "CV-2025-08-3687 (SUCCESS)",
            "display_url": "https://clerkweb.summitoh.net/PublicSite/DisplayImage.asp?gstrPDFOH=vola00000046        00001EAF",
            "expected_id": "vola0000004600001EAF"
        },
        {
            "case": "CV-2025-08-3688 (FAILED)",
            "display_url": "https://clerkweb.summitoh.net/PublicSite/DisplayImage.asp?gstrPDFOH=vola00000046        00001EBE",
            "expected_id": "vola0000004600001EBE"
        }
    ]
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    
    for test_case in test_cases:
        print(f"\n=== {test_case['case']} ===")
        print(f"Original URL: {test_case['display_url']}")
        
        pdf_url = convert_display_image_to_pdf_url(test_case['display_url'])
        print(f"PDF URL: {pdf_url}")
        
        # Test both URLs
        print(f"\nTesting DisplayImage URL:")
        try:
            response = session.get(test_case['display_url'], timeout=10)
            print(f"  Status: {response.status_code}")
            print(f"  Content-Type: {response.headers.get('content-type', 'unknown')}")
            print(f"  Content Length: {len(response.content)}")
            print(f"  First 200 chars: {response.text[:200]}")
        except Exception as e:
            print(f"  Error: {e}")
        
        print(f"\nTesting PDF URL:")
        try:
            response = session.get(pdf_url, timeout=10)
            print(f"  Status: {response.status_code}")
            print(f"  Content-Type: {response.headers.get('content-type', 'unknown')}")
            print(f"  Content Length: {len(response.content)}")
            if response.content.startswith(b'%PDF'):
                print(f"  ✓ Valid PDF content")
            else:
                print(f"  ✗ Not PDF content: {response.content[:100]}")
        except Exception as e:
            print(f"  Error: {e}")

if __name__ == "__main__":
    test_urls()
