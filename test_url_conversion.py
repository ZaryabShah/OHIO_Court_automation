"""
Test script to verify URL conversion is working correctly
"""

from document_downloader import SummitDocumentDownloader

def test_url_conversion():
    downloader = SummitDocumentDownloader()
    
    # Test URLs from your data
    test_urls = [
        "https://clerkweb.summitoh.net/PublicSite/DisplayImage.asp?gstrPDFOH=vola00000042        0000367D",
        "https://clerkweb.summitoh.net/PublicSite/DisplayImage.asp?gstrPDFOH=vola00000041        0000267E", 
        "https://clerkweb.summitoh.net/PublicSite/DisplayImage.asp?gstrPDFOH=vola00000041        0000267F",
        "https://clerkweb.summitoh.net/PublicSite/DisplayImage.asp?gstrPDFOH=vola00000038        00000950",
        "https://clerkweb.summitoh.net/PublicSite/DisplayImage.asp?gstrPDFOH=vola00000038        0000092C"
    ]
    
    print("Testing URL Conversion:")
    print("=" * 80)
    
    for url in test_urls:
        converted_url = downloader.convert_display_image_to_pdf_url(url)
        print(f"Original: {url}")
        print(f"Converted: {converted_url}")
        print("-" * 80)
    
    print("\nExpected patterns:")
    print("https://clerkweb.summitoh.net/PublicSite/Documents/vola000000420000367D.pdf")
    print("https://clerkweb.summitoh.net/PublicSite/Documents/vola000000410000267E.pdf")
    print("https://clerkweb.summitoh.net/PublicSite/Documents/vola000000410000267F.pdf")
    print("https://clerkweb.summitoh.net/PublicSite/Documents/vola00000003800000950.pdf")
    print("https://clerkweb.summitoh.net/PublicSite/Documents/vola000000380000092C.pdf")

if __name__ == "__main__":
    test_url_conversion()
