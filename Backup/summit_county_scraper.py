"""
Summit County Court Records Scraper
Automates the process of searching for foreclosure records on the Summit County website.
"""

import time
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options


class SummitCountyScraper:
    def __init__(self, headless=False):
        """
        Initialize the scraper with Chrome WebDriver
        
        Args:
            headless (bool): Run browser in headless mode (no GUI)
        """
        self.driver = None
        self.wait = None
        self.headless = headless
        self.setup_driver()
    
    def setup_driver(self):
        """Setup Chrome WebDriver with appropriate options"""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 10)
            print("Chrome WebDriver initialized successfully")
        except Exception as e:
            print(f"Error initializing WebDriver: {e}")
            print("Please make sure Chrome and ChromeDriver are installed")
            raise
    
    def navigate_to_search_page(self):
        """Navigate to the initial page and then to the search page"""
        try:
            # Navigate to the initial page
            print("Navigating to Summit County initial page...")
            self.driver.get("https://clerkweb.summitoh.net/PublicSite/SelectDivisionCivil.aspx")
            time.sleep(2)
            
            # Navigate directly to the search page
            print("Navigating to search page...")
            self.driver.get("https://clerkweb.summitoh.net/PublicSite/SearchByMixed.aspx")
            time.sleep(2)
            
            print("Successfully navigated to search page")
            return True
            
        except Exception as e:
            print(f"Error navigating to search page: {e}")
            return False
    
    def enter_search_date(self, search_date):
        """
        Enter the search date in mm/dd/yyyy format
        
        Args:
            search_date (str): Date in mm/dd/yyyy format
        """
        try:
            print(f"Entering search date: {search_date}")
            
            # Find the date input field using the provided XPath
            date_input = self.wait.until(
                EC.presence_of_element_located((
                    By.XPATH, 
                    "/html/body/table[2]/tbody/tr[1]/td/form/table[2]/tbody/tr/td/table/tbody/tr[3]/td[2]/input"
                ))
            )
            
            # Clear any existing content and enter the date
            date_input.clear()
            date_input.send_keys(search_date)
            
            print(f"Date '{search_date}' entered successfully")
            return True
            
        except Exception as e:
            print(f"Error entering search date: {e}")
            return False
    
    def select_foreclosure_option(self):
        """Select 'Foreclosure' from the dropdown menu"""
        try:
            print("Selecting 'Foreclosure' option...")
            
            # Find the dropdown using the provided XPath
            dropdown_element = self.wait.until(
                EC.presence_of_element_located((
                    By.XPATH,
                    "/html/body/table[2]/tbody/tr[1]/td/form/table[2]/tbody/tr/td/table/tbody/tr[7]/td[2]/select"
                ))
            )
            
            # Create Select object and select by visible text
            dropdown = Select(dropdown_element)
            dropdown.select_by_visible_text("Foreclosure")
            
            print("'Foreclosure' option selected successfully")
            return True
            
        except Exception as e:
            print(f"Error selecting foreclosure option: {e}")
            # Try alternative method using keyboard navigation
            try:
                print("Trying alternative method with keyboard navigation...")
                dropdown_element.click()
                time.sleep(0.5)
                dropdown_element.send_keys("f")  # Press 'f' key
                dropdown_element.send_keys(Keys.ENTER)  # Press Enter
                print("'Foreclosure' option selected using keyboard navigation")
                return True
            except Exception as e2:
                print(f"Alternative method also failed: {e2}")
                return False
    
    def click_search_button(self):
        """Click the search button to execute the search"""
        try:
            print("Clicking search button...")
            
            # Find and click the search button
            search_button = self.wait.until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "/html/body/table[2]/tbody/tr[1]/td/form/table[3]/tbody/tr/td/input[1]"
                ))
            )
            
            search_button.click()
            print("Search button clicked successfully")
            
            # Wait for results to load
            time.sleep(3)
            return True
            
        except Exception as e:
            print(f"Error clicking search button: {e}")
            return False
    
    def get_results_html(self):
        """Get the HTML content of the search results page"""
        try:
            print("Retrieving search results HTML...")
            
            # Wait for page to load completely
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # Get the full page HTML
            html_content = self.driver.page_source
            
            print(f"Retrieved HTML content ({len(html_content)} characters)")
            return html_content
            
        except Exception as e:
            print(f"Error retrieving HTML content: {e}")
            return None
    
    def save_html_to_file(self, html_content, filename=None):
        """
        Save HTML content to a file
        
        Args:
            html_content (str): HTML content to save
            filename (str): Optional filename, defaults to timestamp-based name
        """
        try:
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"summit_county_results_{timestamp}.html"
            
            # Ensure the results directory exists
            results_dir = "results"
            if not os.path.exists(results_dir):
                os.makedirs(results_dir)
            
            filepath = os.path.join(results_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as file:
                file.write(html_content)
            
            print(f"HTML content saved to: {filepath}")
            return filepath
            
        except Exception as e:
            print(f"Error saving HTML to file: {e}")
            return None
    
    def search_foreclosure_records(self, search_date, save_to_file=True):
        """
        Complete workflow to search for foreclosure records
        
        Args:
            search_date (str): Date in mm/dd/yyyy format
            save_to_file (bool): Whether to save results to file
            
        Returns:
            str: HTML content of results or None if failed
        """
        try:
            print(f"Starting foreclosure records search for date: {search_date}")
            
            # Step 1: Navigate to search page
            if not self.navigate_to_search_page():
                return None
            
            # Step 2: Enter search date
            if not self.enter_search_date(search_date):
                return None
            
            # Step 3: Select foreclosure option
            if not self.select_foreclosure_option():
                return None
            
            # Step 4: Click search button
            if not self.click_search_button():
                return None
            
            # Step 5: Get results HTML
            html_content = self.get_results_html()
            
            if html_content and save_to_file:
                self.save_html_to_file(html_content)
            
            print("Search completed successfully!")
            return html_content
            
        except Exception as e:
            print(f"Error during search process: {e}")
            return None
    
    def close(self):
        """Close the browser and clean up resources"""
        if self.driver:
            self.driver.quit()
            print("Browser closed successfully")


def main():
    """Main function to demonstrate the scraper usage"""
    
    # Example usage
    scraper = SummitCountyScraper(headless=False)  # Set to True to run without GUI
    
    try:
        # Search for today's date (you can change this to any date in mm/dd/yyyy format)
        # today = datetime.now().strftime("%m/%d/%Y")
        today = "08/08/2024"  # Example date for testing
        # You can also specify a custom date like this:
        # search_date = "01/15/2024"
        
        print(f"Searching for foreclosure records on: {today}")
        
        # Perform the search
        results_html = scraper.search_foreclosure_records(today)
        
        if results_html:
            print("Search completed successfully!")
            print(f"Results HTML length: {len(results_html)} characters")
        else:
            print("Search failed!")
    
    except KeyboardInterrupt:
        print("\nSearch interrupted by user")
    
    except Exception as e:
        print(f"Unexpected error: {e}")
    
    finally:
        # Always close the browser
        scraper.close()


if __name__ == "__main__":
    main()
