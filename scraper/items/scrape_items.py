from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from datetime import datetime, timedelta
import time
from pathlib import Path

def setup_driver(): # Want to remove terminal noise
    """Setup and return Chrome WebDriver with options"""
    chrome_options = Options()
    chrome_options.add_argument("--silent")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--disable-logging")
    
    return webdriver.Chrome(options=chrome_options)

def handle_consent_popup(driver): # Find and click consent button by class
    """Handle consent popup on the website"""
    try:
        consent_button = driver.find_element(By.CSS_SELECTOR, "button.fc-button.fc-cta-consent.fc-primary-button")
        if consent_button.is_displayed() and consent_button.is_enabled():
            consent_button.click()
            print("Consent button clicked")
            time.sleep(2)
    except:
        pass # No consent popup found, which is fine

def check_file_freshness(file_path, days=30): # Function to allow us to resume if the .py crashes. Huge time saver.
    """Check if a file exists and is less than specified days old"""
    
    if not Path(file_path).exists():
        return False, None # File is old because it doesn't exist
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            timestamp_str = f.readline().strip() # First line is the timestamp string of last scrape
            file_timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S') # String parse the timestamp to a datetime object
            
            now = datetime.now()
            time_diff = now - file_timestamp # Calculate the time difference between now and the last scrape
            
            return time_diff < timedelta(days=days), True # Return True if the file is less than 30 days old, second value is True since the file exists
    except Exception as e:
        print(f"Error reading timestamp from {file_path}: {e}") # File exists but error with Timestamp
        return False, True

def save_with_timestamp(file_path, content_func, data, *args):
    """Save content to file with timestamp, using content_func to generate the content"""
    scraped_data_dir = Path(file_path).parent # folder for the file
    if not scraped_data_dir.exists(): # If the folder doesn't exist, create it and all parent folders if needed
        scraped_data_dir.mkdir(parents=True, exist_ok=True)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        if args:
            content_func(f, data, *args)
        else:
            content_func(f, data)

def find_raid_urls(driver):
    """Find and return all raid URLs"""
    raid_links_file = Path(__file__).parent / "scraped_items" / "raid_links.txt"
    
    # Check if file exists and is less than 30 days old
    is_fresh, file_exists = check_file_freshness(raid_links_file, days=30)
    
    if is_fresh:
        print("Raid URLs file is less than 30 days old, reading from file...")
        
        # Read raid URLs from file (skip timestamp and comments)
        raid_urls = []
        with open(raid_links_file, 'r', encoding='utf-8') as f:
            f.readline()  # Skip timestamp
            lines = f.readlines()
            current_raid = None
            
            for line in lines:
                line = line.strip()
                if line.startswith('#') and 'Total raids found:' not in line: # Raid names
                    current_raid = line[2:].strip()  # Don't include '# ' prefix
                elif line.startswith('http') and current_raid:
                    # This is a URL for the current raid
                    raid_urls.append({
                        'name': current_raid,
                        'url': line
                    })
                    current_raid = None # Reset current raid name
        
        print(f"Read {len(raid_urls)} raid URLs from file")
        return raid_urls # Load existing raid URLs
    else: # is_fresh is False
        if file_exists: # file_exists is True
            print("Raid URLs file is older than 30 days.")
        else: # file_exists is False
            print("Raid URLs file not found.")
    
    # Only enter this code if new scraping is needed
    print("Finding raid URLs...")
    
    # Click raid button
    raid_button = driver.find_element(By.CSS_SELECTOR, "button.header-bottom-bar__item.header-bottom-bar__item--raid-content.warcraft")
    raid_button.click()
    time.sleep(3)
    
    # Extract raid URLs from specific divs
    dropdown = driver.find_element(By.CSS_SELECTOR, ".header__menu-wrapper--content")
    raid_divs = dropdown.find_elements(By.CSS_SELECTOR, ".header-section-header__content-title")
    raid_urls = []
    
    for div in raid_divs:
        link = div.find_element(By.TAG_NAME, "a")
        href = link.get_attribute("href")
        raid_name = link.text.strip()
        
        if href and raid_name:
            raid_urls.append({
                'name': raid_name,
                'url': href
            })
    
    # Save raid URLs to file
    def save_raid_urls_content(f, raid_urls):
        f.write(f"# Total raids found: {len(raid_urls)}\n\n")
        for raid in raid_urls:
            f.write(f"# {raid['name']}\n")
            f.write(f"{raid['url']}\n\n")
    
    save_with_timestamp(raid_links_file, save_raid_urls_content, raid_urls)
    print(f"Found {len(raid_urls)} raid URLs and saved to {raid_links_file}")
    return raid_urls

def find_class_spec_extensions(driver, first_raid_url):
    """Find and return all class/spec extensions"""
    class_links_file = Path(__file__).parent / "scraped_items" / "class_links.txt"
    
    # Check if file exists and is less than 30 days old
    is_fresh, file_exists = check_file_freshness(class_links_file, days=30)
    
    if is_fresh:
        print("Class/spec extensions file is less than 30 days old, reading from file...")
        
        # Read class/spec extensions from file (skip timestamp and comments)
        class_spec_extensions = []
        with open(class_links_file, 'r', encoding='utf-8') as f:
            f.readline()  # Skip timestamp
            lines = f.readlines()
            current_class_spec = None
            
            for line in lines:
                line = line.strip()
                if line.startswith('#') and 'Total class/spec combinations:' not in line: # Class-spec names
                    current_class_spec = line[2:].strip()  # Remove '# ' prefix
                elif line.startswith('?') and current_class_spec:
                    # This is an extension for the current class-spec
                    class_name, spec_name = current_class_spec.split(' - ')
                    class_spec_extensions.append({
                        'class': class_name,
                        'spec': spec_name,
                        'extension': line[1:]  # Remove '?' prefix
                    })
                    current_class_spec = None
        
        print(f"Read {len(class_spec_extensions)} class/spec extensions from file")
        return class_spec_extensions # Load existing class/spec extensions
    else: # is_fresh is False
        if file_exists: # file_exists is True
            print("Class/spec extensions file is older than 30 days.")
        else: # file_exists is False
            print("Class/spec extensions file not found.")
    
    # Only enter this code if new scraping is needed
    print("Finding class/spec extensions...")
    
    # Navigate to the first raid page
    driver.get(first_raid_url)
    time.sleep(5)
    
    # Look for the class selection container
    try:
        class_container = driver.find_element(By.CSS_SELECTOR, "#filter-class-selection-container")
        class_container.click()
        time.sleep(2)
        
        all_li_elements = class_container.find_elements(By.CSS_SELECTOR, "li") # Get all li elements in the dropdown
        
        if len(all_li_elements) >= 3: # First 2 elements are not class extensions
            class_li_elements = all_li_elements[2:]
            
            class_spec_extensions = []
            
            for class_li in class_li_elements:
                try:
                    class_link = class_li.find_element(By.TAG_NAME, "a") # Find the <a> tag inside this li
                    onmouseenter = class_link.get_attribute("onmouseenter") # onmouseenter is the attribute that contains the function call setClassAndSpec('Class', 'Spec')
                    
                    if onmouseenter and "setClassAndSpec" in onmouseenter: # If the attribute contains the function call setClassAndSpec
                        params = onmouseenter[onmouseenter.find("(") + 1:onmouseenter.rfind(")")].replace("'", "").split(", ") # Extract the parameters
                        
                        if len(params) >= 2: # If there are at least 2 parameters
                            class_name = params[0] # First parameter is the class name
                            spec_name = params[1] # Second parameter is the spec name
                            
                            if spec_name != 'Any':
                                spec_extension = f"class={class_name}&spec={spec_name}" # Store just the query parameters
                                class_spec_extensions.append({
                                    'class': class_name,
                                    'spec': spec_name,
                                    'extension': spec_extension
                                })
                                
                except Exception as e:
                    pass
            
            def save_class_spec_content(f, class_spec_extensions): # Save the class/spec extensions to the file
                f.write(f"# Total class/spec combinations: {len(class_spec_extensions)}\n\n")
                for ext_info in class_spec_extensions:
                    f.write(f"# {ext_info['class']} - {ext_info['spec']}\n")
                    f.write(f"?{ext_info['extension']}\n\n")
            
            save_with_timestamp(class_links_file, save_class_spec_content, class_spec_extensions)
            print(f"Found {len(class_spec_extensions)} class/spec extensions and saved to {class_links_file}")
            return class_spec_extensions
        else:
            print(f"Not enough li elements found. Expected at least 3, got {len(all_li_elements)}")
            return []
            
    except Exception as e:
        print(f"Error with class selection container: {e}")
        return []

def save_players(driver, raid_urls, class_spec_extensions):
    """Save player HTML for each raid/class/spec combination"""
    print("Starting player data scraping...")
    
    boss_parameters = { # Some Raids have specific link additions
        "Ruins of Ahn'Qiraj": "&boss=150720",
        "Zul'Gurub": "&boss=150785&partition=2", 
        "Onyxia": "&boss=201084&partition=1"
    }
    
    total_combinations = len(raid_urls) * len(class_spec_extensions)
    current_combination = 0
    
    for raid in raid_urls:
        raid_name = raid['name']
        raid_url = raid['url']
        
        print(f"\nProcessing raid: {raid_name}")
        
        for ext_info in class_spec_extensions:
            current_combination += 1
            class_name = ext_info['class']
            spec_name = ext_info['spec']
            extension = ext_info['extension']
            
            full_url = f"{raid_url}?{extension}" # Create the full URL for this combination
            
            if raid_name in boss_parameters: # Add boss parameter if this raid needs it
                full_url += boss_parameters[raid_name]
            
            raid_folder = Path(__file__).parent / "scraped_items" / raid_name
            class_folder = raid_folder / class_name # Path recognises these as paths so / works
            spec_file = class_folder / f"{spec_name}.txt"
            
            is_fresh, file_exists = check_file_freshness(spec_file, days=30) # Check if this specific file is fresh (within 30 days)
            
            if is_fresh:
                print(f"{class_name} - {spec_name} (fresh, skipping)")
                continue
        
            print(f"{class_name} - {spec_name} ({current_combination}/{total_combinations})") # If current combination is not fresh, print the current combination
            
            try:
                driver.get(full_url) # Navigate to the page
                time.sleep(3)
                
                handle_consent_popup(driver) # Handle consent popups if they appear again
                time.sleep(1)
                
                table = driver.find_element(By.CSS_SELECTOR, "table.summary-table.ranking-table.players-table.dataTable.no-footer") # Find the players table
                expand_buttons = driver.find_elements(By.CSS_SELECTOR, "span.disclosure.zmdi.zmdi-caret-down[data-expanded='false']") # Find the expand buttons
                
                for button in expand_buttons:
                    try:
                        driver.execute_script("arguments[0].scrollIntoView(true); arguments[0].click();", button) # Content seems to be javascript so this is needed
                        time.sleep(0.1)
                    except Exception as e:
                        print(f"Could not expand a player: {e}")
                        continue
                
                print(f"All player rows expanded, capturing HTML...")
                
                table_html = table.get_attribute('outerHTML') # Get the HTML of the table
                
                def save_table_content(f, table_html, raid_name, full_url):
                    f.write(f"# Raid: {raid_name}\n")
                    f.write(f"# URL: {full_url}\n")
                    f.write(f"# Scraped: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    f.write(table_html)
                
                save_with_timestamp(spec_file, save_table_content, table_html, raid_name, full_url)
                print(f"Saved table HTML to {spec_file}")
                
                time.sleep(1)
                
            except Exception as e:
                print(f"Error scraping {class_name} - {spec_name} for {raid_name}: {e}")
                continue
    
    print(f"\n Completed player data scraping! Processed {current_combination} combinations.")

def main():
    """Main function to find raids and class/spec extensions"""
    print("Scraping Warcraft Logs Fresh...")
    
    try:
        driver = setup_driver()
        driver.get("https://fresh.warcraftlogs.com/")
        time.sleep(3)
        
        handle_consent_popup(driver) # Click consent button
        
        raid_urls = find_raid_urls(driver) # Load or scrape raid URLs
        
        if raid_urls:
            class_spec_extensions = find_class_spec_extensions(driver, raid_urls[0]['url']) # Only need to scrape the first raid URL
            
            print(f"\n{'='*60}")
            print(f"FINAL RESULTS")
            print(f"{'='*60}")
            print(f"Total raids found: {len(raid_urls)}")
            print(f"Total class/spec combinations: {len(class_spec_extensions)}")
            print(f"Total URLs: {len(class_spec_extensions) * len(raid_urls)}")
            
            if class_spec_extensions:
                save_players(driver, raid_urls, class_spec_extensions)

        time.sleep(15)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
