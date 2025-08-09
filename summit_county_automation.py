"""
Integrated Summit County Court Records Automation
Combines scraping and parsing functionality for complete court records automation.
"""

import os
import sys
from datetime import datetime, timedelta
from summit_county_scraper import SummitCountyScraper
from summit_county_parser import SummitCountyParser


class SummitCountyAutomation:
    """Integrated automation for Summit County court records"""
    
    def __init__(self, headless=False):
        """
        Initialize the automation system
        
        Args:
            headless (bool): Run browser in headless mode
        """
        self.scraper = SummitCountyScraper(headless=headless)
        self.parser = SummitCountyParser()
        self.results_dir = "results"
        
        # Ensure results directory exists
        if not os.path.exists(self.results_dir):
            os.makedirs(self.results_dir)
    
    def search_and_parse(self, search_date: str, save_formats=['json', 'csv'], auto_save=True):
        """
        Complete workflow: search for records and parse the results
        
        Args:
            search_date (str): Date in mm/dd/yyyy format
            save_formats (list): List of formats to save ('json', 'csv', 'html')
            auto_save (bool): Whether to automatically save results
            
        Returns:
            tuple: (html_content, parsed_cases, metadata)
        """
        try:
            print(f"Starting automated search and parse for date: {search_date}")
            
            # Step 1: Scrape the data
            print("\n" + "="*60)
            print("STEP 1: SCRAPING DATA")
            print("="*60)
            
            html_content = self.scraper.search_foreclosure_records(
                search_date, 
                save_to_file=('html' in save_formats) and auto_save
            )
            
            if not html_content:
                print("Failed to scrape data")
                return None, [], {}
            
            # Step 2: Parse the data
            print("\n" + "="*60)
            print("STEP 2: PARSING DATA")
            print("="*60)
            
            parsed_cases = self.parser.parse_html_content(html_content)
            metadata = self.parser.get_search_metadata()
            
            # Step 3: Save parsed data
            if auto_save and parsed_cases:
                print("\n" + "="*60)
                print("STEP 3: SAVING PARSED DATA")
                print("="*60)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                if 'json' in save_formats:
                    json_file = os.path.join(self.results_dir, f"parsed_cases_{timestamp}.json")
                    self.parser.save_cases_to_json(parsed_cases, json_file)
                
                if 'csv' in save_formats:
                    csv_file = os.path.join(self.results_dir, f"parsed_cases_{timestamp}.csv")
                    self.parser.save_cases_to_csv(parsed_cases, csv_file)
            
            # Step 4: Display summary
            print("\n" + "="*60)
            print("STEP 4: RESULTS SUMMARY")
            print("="*60)
            
            self.parser.print_cases_summary(parsed_cases)
            
            return html_content, parsed_cases, metadata
            
        except Exception as e:
            print(f"Error in search_and_parse: {e}")
            return None, [], {}
    
    def search_date_range(self, start_date: str, end_date: str, save_formats=['json', 'csv']):
        """
        Search for multiple dates in a range
        
        Args:
            start_date (str): Start date in mm/dd/yyyy format
            end_date (str): End date in mm/dd/yyyy format
            save_formats (list): List of formats to save
            
        Returns:
            dict: Results for each date
        """
        try:
            start_dt = datetime.strptime(start_date, '%m/%d/%Y')
            end_dt = datetime.strptime(end_date, '%m/%d/%Y')
            
            all_results = {}
            current_date = start_dt
            
            while current_date <= end_dt:
                date_str = current_date.strftime('%m/%d/%Y')
                print(f"\n{'='*80}")
                print(f"SEARCHING FOR DATE: {date_str}")
                print('='*80)
                
                html_content, cases, metadata = self.search_and_parse(
                    date_str, 
                    save_formats=save_formats
                )
                
                all_results[date_str] = {
                    'cases': cases,
                    'metadata': metadata,
                    'count': len(cases)
                }
                
                # Move to next day
                current_date += timedelta(days=1)
                
                # Add a small delay between requests to be respectful
                if current_date <= end_dt:
                    print("Waiting 2 seconds before next request...")
                    import time
                    time.sleep(2)
            
            # Print overall summary
            self._print_date_range_summary(all_results)
            
            return all_results
            
        except ValueError as e:
            print(f"Invalid date format: {e}")
            return {}
        except Exception as e:
            print(f"Error in search_date_range: {e}")
            return {}
    
    def _print_date_range_summary(self, results: dict):
        """Print summary for date range search"""
        print(f"\n{'='*80}")
        print("DATE RANGE SEARCH SUMMARY")
        print('='*80)
        
        total_cases = 0
        for date_str, data in results.items():
            case_count = data['count']
            total_cases += case_count
            print(f"{date_str}: {case_count} cases")
        
        print(f"\nTOTAL CASES ACROSS ALL DATES: {total_cases}")
        print('='*80)
    
    def search_recent_days(self, days: int = 7, save_formats=['json', 'csv']):
        """
        Search for the last N days
        
        Args:
            days (int): Number of recent days to search
            save_formats (list): List of formats to save
            
        Returns:
            dict: Results for each date
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days-1)
        
        start_str = start_date.strftime('%m/%d/%Y')
        end_str = end_date.strftime('%m/%d/%Y')
        
        print(f"Searching for the last {days} days ({start_str} to {end_str})")
        
        return self.search_date_range(start_str, end_str, save_formats)
    
    def close(self):
        """Close the scraper and clean up resources"""
        self.scraper.close()


def main():
    """Main function demonstrating the integrated automation"""
    
    automation = SummitCountyAutomation(headless=False)
    
    try:
        # Get today's date
        today = datetime.now().strftime("%m/%d/%Y")
        
        print("Summit County Court Records Automation")
        print("=====================================")
        print("\nOptions:")
        print("1. Search for a specific date")
        print("2. Search for a date range")
        print("3. Search for the last 7 days")
        print("4. Parse existing HTML file")
        print("5. Exit")
        
        while True:
            choice = input("\nSelect an option (1-5): ").strip()
            
            if choice == '1':
                # Search for specific date
                date_input = input(f"Enter date to search (MM/DD/YYYY) or press Enter for today ({today}): ").strip()
                search_date = date_input if date_input else today
                
                try:
                    # Validate date format
                    datetime.strptime(search_date, '%m/%d/%Y')
                    
                    html_content, cases, metadata = automation.search_and_parse(
                        search_date, 
                        save_formats=['json', 'csv', 'html']
                    )
                    
                    if cases:
                        print(f"\nFound {len(cases)} cases for {search_date}")
                    else:
                        print(f"No cases found for {search_date}")
                        
                except ValueError:
                    print("Invalid date format. Please use MM/DD/YYYY format.")
            
            elif choice == '2':
                # Search for date range
                start_date = input("Enter start date (MM/DD/YYYY): ").strip()
                end_date = input("Enter end date (MM/DD/YYYY): ").strip()
                
                try:
                    # Validate date formats
                    datetime.strptime(start_date, '%m/%d/%Y')
                    datetime.strptime(end_date, '%m/%d/%Y')
                    
                    results = automation.search_date_range(start_date, end_date)
                    
                except ValueError:
                    print("Invalid date format. Please use MM/DD/YYYY format.")
            
            elif choice == '3':
                # Search for last 7 days
                days_input = input("Enter number of recent days to search (default 7): ").strip()
                days = int(days_input) if days_input.isdigit() else 7
                
                results = automation.search_recent_days(days)
            
            elif choice == '4':
                # Parse existing HTML file
                html_file = input("Enter path to HTML file: ").strip()
                
                if os.path.exists(html_file):
                    parser = SummitCountyParser()
                    cases = parser.parse_html_file(html_file)
                    
                    if cases:
                        parser.print_cases_summary(cases)
                        
                        # Save parsed data
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        json_file = f"results/parsed_existing_{timestamp}.json"
                        csv_file = f"results/parsed_existing_{timestamp}.csv"
                        
                        parser.save_cases_to_json(cases, json_file)
                        parser.save_cases_to_csv(cases, csv_file)
                    else:
                        print("No cases found in the HTML file")
                else:
                    print("File not found")
            
            elif choice == '5':
                # Exit
                break
            
            else:
                print("Invalid choice. Please select 1-5.")
    
    except KeyboardInterrupt:
        print("\nOperation interrupted by user")
    
    except Exception as e:
        print(f"Unexpected error: {e}")
    
    finally:
        automation.close()
        print("\nAutomation completed.")


if __name__ == "__main__":
    main()
