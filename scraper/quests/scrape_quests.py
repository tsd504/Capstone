import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from pathlib import Path
import time
import re
from datetime import datetime, timedelta
import scrape_comments

def setup_driver():
    """Setup Chrome WebDriver"""
    chrome_options = Options()
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--silent")
    chrome_options.add_argument("--disable-logging")
    return webdriver.Chrome(options=chrome_options)

def find_quest_categories(driver):
    """Find all quest category URL extensions from the dropdown menus"""
    quest_groups = {}
    
    try:
        # Find and hover over quests menu
        quests_link = driver.find_element(By.CSS_SELECTOR, "span.menu-buttons a[href='?quests']")
        ActionChains(driver).move_to_element(quests_link).perform()
        time.sleep(1)
        
        # Get first level categories
        first_level_links = driver.find_element(By.CSS_SELECTOR, "div.menu").find_elements(By.CSS_SELECTOR, "a[href^='?quests']")
        
        # Process each category (skip last)
        for link in first_level_links[:-1]:
            try:
                extension = link.get_attribute("href").split("classicdb.ch")[-1]
                if "=" in extension:
                    first_level = extension.split("=")[1]
                    quest_groups.setdefault(first_level, [])
                    
                    # Hover to get subcategories
                    ActionChains(driver).move_to_element(link).perform()
                    time.sleep(1)
                    
                    # Get subcategory links
                    subcategory_links = driver.find_element(By.CSS_SELECTOR, "div.menu:nth-of-type(2)").find_elements(By.CSS_SELECTOR, "a[href^='?quests']")
                    
                    for sub_link in subcategory_links:
                        sub_href = sub_link.get_attribute("href")
                        if sub_href and "?quests" in sub_href:
                            sub_extension = sub_href.split("classicdb.ch")[-1]
                            sub_text = sub_link.text.strip()
                            
                            # Avoid duplicates
                            if not any(item['extension'] == sub_extension for item in quest_groups[first_level]):
                                quest_groups[first_level].append({
                                    'extension': sub_extension,
                                    'category_name': sub_text
                                })
                                
            except Exception as e:
                print(f"Error processing link: {e}")
                continue

        return quest_groups
        
    except Exception as e:
        print(f"Error finding quest categories: {e}")
        return {}

def check_file_freshness(file_path, days=30):
    """Check if a file is less than specified days old"""
    
    if not Path(file_path).exists():
        return False
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            f.readline()  # Skip first line
            timestamp_line = f.readline().strip()  # Read second line
            
            if timestamp_line.startswith('# Generated:'):
                timestamp_str = timestamp_line.replace('# Generated:', '').strip()
                file_timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                
                now = datetime.now()
                return now - file_timestamp < timedelta(days=days)
            
            return False
            
    except Exception as e:
        print(f"Error reading timestamp from {file_path}: {e}")
        return False

def extract_quest_data_from_row(row, driver):
    """Extract quest data from a table row"""
    try:
        cells = row.find_elements(By.TAG_NAME, "td")
        if len(cells) < 4:
            return None
        
        # Extract basic quest info
        name_link = cells[0].find_element(By.TAG_NAME, "a")
        quest_name = name_link.text.strip().replace('\n', ' ').replace('\r', ' ').replace('  ', ' ')
        quest_url = name_link.get_attribute("href")
        quest_extension = quest_url.split("classicdb.ch")[-1] if quest_url and "classicdb.ch" in quest_url else quest_url
        
        level = cells[1].text.strip().replace('\n', ' ').replace('\r', ' ').replace('  ', ' ') if len(cells) > 1 else ""
        req_level = cells[2].text.strip().replace('\n', ' ').replace('\r', ' ').replace('  ', ' ') if len(cells) > 2 else ""
        
        # Extract faction
        faction = "Both"
        if len(cells) > 3:
            faction_cell = cells[3]
            try:
                # Look for span with faction class
                faction_span = faction_cell.find_element(By.CSS_SELECTOR, "span")
                if faction_span:
                    span_class = faction_span.get_attribute("class")
                    if span_class == "alliance-icon":
                        faction = "Alliance"
                    elif span_class == "horde-icon":
                        faction = "Horde"
                    # If class is empty or doesn't match, faction remains "Both"
            except:
                pass
        
        # Extract rewards
        rewards = ""
        rewards_parts = []
        
        if len(cells) > 4:
            rewards_cell = cells[4]

            pick_items = []
            guaranteed_items = []
            base_rewards = []
            
            # Iterate through direct child divs of the rewards td
            for div in rewards_cell.find_elements(By.TAG_NAME, "div"):
                # Skip clear divs
                if div.get_attribute("class") == "clear":
                    continue
                
                # Look for the first child div (position: relative; width: 1px)
                try:
                    first_child = div.find_element(By.CSS_SELECTOR, "div[style*='position: relative'][style*='width: 1px']")
                    
                    # Look for the second child div (class="q0") that contains the text
                    try:
                        second_child = first_child.find_element(By.CSS_SELECTOR, "div.q0")
                        text_content = second_child.text.strip()
                        
                        if "Pick:" in text_content:
                            # Get items from iconsmall divs that are siblings to the first child
                            iconsmall_divs = div.find_elements(By.CSS_SELECTOR, "div.iconsmall")
                            
                            for iconsmall in iconsmall_divs:
                                try:
                                    item_link = iconsmall.find_element(By.CSS_SELECTOR, "a")
                                    item_url = item_link.get_attribute("href")
                                    quantity = item_link.get_attribute("rel") or "1"
                                    if item_url and "?item=" in item_url:
                                        item_extension = item_url.split("classicdb.ch")[-1] if "classicdb.ch" in item_url else item_url
                                        item_with_quantity = f"{item_extension} {quantity}" if quantity != "1" else item_extension
                                        if item_with_quantity not in pick_items:
                                            pick_items.append(item_with_quantity)
                                except:
                                    pass
                        
                        elif "Also get:" in text_content:
                            # Get items from iconsmall divs that are siblings to the first child
                            iconsmall_divs = div.find_elements(By.CSS_SELECTOR, "div.iconsmall")
                            
                            for iconsmall in iconsmall_divs:
                                try:
                                    item_link = iconsmall.find_element(By.CSS_SELECTOR, "a")
                                    item_url = item_link.get_attribute("href")
                                    quantity = item_link.get_attribute("rel") or "1"
                                    if item_url and "?item=" in item_url:
                                        item_extension = item_url.split("classicdb.ch")[-1] if "classicdb.ch" in item_url else item_url
                                        item_with_quantity = f"{item_extension} {quantity}" if quantity != "1" else item_extension
                                        if item_with_quantity not in guaranteed_items:
                                            guaranteed_items.append(item_with_quantity)
                                except:
                                    pass
                    
                    except:
                        # No second child with class="q0" found
                        pass
                
                except:
                    # No first child div found, check if this div directly contains XP or items
                    div_text = div.text.strip()
                    if "XP" in div_text:
                        if div_text not in base_rewards:
                            base_rewards.append(div_text)
            
            # Also check for any iconsmall divs that weren't caught by the labeled sections
            all_iconsmall_divs = rewards_cell.find_elements(By.CSS_SELECTOR, "div.iconsmall")
            for iconsmall in all_iconsmall_divs:
                try:
                    item_link = iconsmall.find_element(By.CSS_SELECTOR, "a")
                    item_url = item_link.get_attribute("href")
                    quantity = item_link.get_attribute("rel") or "1"
                    if item_url and "?item=" in item_url:
                        item_extension = item_url.split("classicdb.ch")[-1] if "classicdb.ch" in item_url else item_url
                        item_with_quantity = f"{item_extension} {quantity}" if quantity != "1" else item_extension
                        # Check if this item is already in pick or guaranteed lists
                        if item_with_quantity not in pick_items and item_with_quantity not in guaranteed_items:
                            guaranteed_items.append(item_with_quantity)
                except:
                    pass
            
        # Build the final rewards string
        if base_rewards:
            rewards_parts.extend(base_rewards)
        
        if pick_items:
            rewards_parts.append(f"Pick: [{', '.join(pick_items)}]")
        
        if guaranteed_items:
            for item in guaranteed_items:
                rewards_parts.append(f"Item: {item}")
        
        # Combine all reward parts
        if rewards_parts:
            rewards = " | ".join(rewards_parts)
        
        return {
            'name': quest_name,
            'url': quest_url,
            'extension': quest_extension,
            'level': level,
            'required_level': req_level,
            'faction': faction,
            'rewards': rewards
        }
    except Exception as e:
        print(f"Error extracting data from row: {e}")
        return None

def scrape_quest_page(driver, extension, category):
    """Scrape all quests from all pages for a single extension"""
    all_quests, page_num = [], 1
    
    while True:
        print(f"Scraping page {page_num}...")
        
        try:
            # Find table with quest data (multiple columns)
            quest_table = next((table for table in driver.find_elements(By.TAG_NAME, "table")
                              if len(table.find_elements(By.TAG_NAME, "tr")) > 1 and
                              len(table.find_elements(By.TAG_NAME, "tr")[1].find_elements(By.TAG_NAME, "td")) >= 4), None)
            
            if not quest_table:
                print(f"No quest table with data found on page {page_num}")
                break
            
            # Extract quests from rows
            page_quests = []
            for row in quest_table.find_elements(By.TAG_NAME, "tr")[1:]:
                quest_data = extract_quest_data_from_row(row, driver)
                if quest_data:
                    quest_data['category'] = category
                    page_quests.append(quest_data)
            
            all_quests.extend(page_quests)
            print(f"Found {len(page_quests)} quests on page {page_num} (Total: {len(all_quests)})")
            
            # Try next page
            next_buttons = driver.find_elements(By.CSS_SELECTOR, "a[href='javascript:;']")
            next_button = next((btn for btn in next_buttons if "Next" in btn.text), None)
            
            if next_button:
                next_button.click()
                time.sleep(1)
                page_num += 1
            else:
                break
                
        except Exception as e:
            print(f"No table with data found on page {page_num}: {e}")
            break

    return all_quests

def save_quests_to_file(quests, category, subcategory):
    """Save quests to a file in the appropriate folder structure"""
    # Create folder structure
    category_folder = Path(__file__).parent / "scraped_quests" / category
    if not category_folder.exists():
        category_folder.mkdir(parents=True, exist_ok=True)
    
    # Create filename from subcategory
    filename = subcategory.replace(" ", "_").replace("/", "_").replace("\\", "_") + ".txt"
    filepath = category_folder / filename
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"# Quest Data for {category} - {subcategory}\n")
        f.write(f"# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Total quests: {len(quests)}{' (No quests found)' if not quests else ''}\n\n")
        
        f.write("Quest Extension\tName\tLevel\tRequired Level\tFaction\tRewards\tCategory\n")
        for quest in quests:
            f.write(f"{quest['extension']}\t{quest['name']}\t{quest['level']}\t{quest['required_level']}\t{quest['faction']}\t{quest['rewards']}\t{quest['category']}\n")
    
    message = f"Created empty file for {subcategory} (no quests found)" if not quests else f"Saved {len(quests)} quests to {filepath}"
    print(message)

def collect_unique_items_from_files():
    """Collect unique item extensions from existing quest files"""
    print("Scanning quest files for unique item extensions...")
    unique_items = set()
    excluded_files = {"quest_extensions.txt", "item_lookup.txt"}
    
    for filepath in (Path(__file__).parent / "scraped_quests").rglob("*.txt"):
        if filepath.name not in excluded_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        # Skip comment lines and empty lines
                        if line.startswith('#') or not line.strip():
                            continue
                        
                        # Split by tabs to get columns
                        parts = line.strip().split('\t')
                        if len(parts) >= 6:  # Ensure I have at least 6 columns
                            rewards_column = parts[5]  # Column 6 (0-indexed as 5)
                            
                            # Find all item extensions in the rewards column only
                            item_matches = re.findall(r'/?item=\d+', rewards_column)
                            # Ensure all matches have the correct format /?item=ID
                            item_matches = [f"/?item={match.split('=')[-1]}" for match in item_matches]
                            unique_items.update(item_matches)
                
            except Exception as e:
                print(f"Error scanning {filepath}: {e}")
    
    print(f"Found {len(unique_items)} unique item extensions in quest files")
    return unique_items

def create_item_lookup_file(driver): # Similar to create_weapon_lookup.py but for quest rewards
    """Create or update lookup file with unique item extensions and their names"""
    # Collect unique items from existing files
    unique_items = collect_unique_items_from_files()
    
    if not unique_items:
        print("No unique items found to process")
        return
    
    # Load existing item IDs from lookup file
    lookup_file = Path(__file__).parent / "scraped_quests" / "item_lookup.txt"
    existing_item_ids = set()
    
    if lookup_file.exists():
        with open(lookup_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith("/?item="):
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        existing_item_ids.add(parts[0].strip())
        print(f"Loaded {len(existing_item_ids)} existing item IDs")
    
    # Find new items to lookup
    items_to_lookup = [item for item in unique_items if item not in existing_item_ids]
    
    if not items_to_lookup:
        print("All items already have names")
        return
    
    print(f"Looking up {len(items_to_lookup)} new items...")
    
    # Append new items
    with open(lookup_file, 'a', encoding='utf-8') as f:
        for i, item_extension in enumerate(items_to_lookup, 1):
            try:
                # Ensure the item extension starts with /?item=
                if not item_extension.startswith('/?item='):
                    item_extension = f"/?item={item_extension.split('=')[-1]}"
                url = f"https://classicdb.ch{item_extension}"
                driver.get(url)
                
                # Wait for page to load
                WebDriverWait(driver, 5).until(
                    lambda d: d.find_element(By.CSS_SELECTOR, "div.text")
                )
                
                text_div = driver.find_element(By.CSS_SELECTOR, "div.text")
                item_name = text_div.find_element(By.TAG_NAME, "h1").text.strip()
                
                if item_name and len(item_name) > 2:
                    f.write(f"{item_extension}\t{item_name}\n")
                    print(f"  {i}/{len(items_to_lookup)}: {item_name}")
                else:
                    f.write(f"{item_extension}\tUnknown Item\n")
                    print(f"  {i}/{len(items_to_lookup)}: Unknown Item")
                    
            except Exception as e:
                f.write(f"{item_extension}\tUnknown Item\n")
                print(f"  {i}/{len(items_to_lookup)}: Error - {e}")
    
    print(f"Added {len(items_to_lookup)} new items")

def replace_item_extensions_with_names():
    """Replace item extensions with names in all quest files"""
    lookup_file = Path(__file__).parent / "scraped_quests" / "item_lookup.txt"
    if not lookup_file.exists():
        print("Item lookup file not found")
        return
    
    # Load item mappings
    with open(lookup_file, 'r', encoding='utf-8') as f:
        item_mapping = {parts[0].strip(): parts[1].strip() 
                       for line in f if line.startswith("/?item=") 
                       and len(parts := line.strip().split('\t')) >= 2}
    
    print(f"Loaded {len(item_mapping)} item mappings")
    
    # Process quest files
    quest_files_processed = replacements_made = 0
    excluded_files = {"quest_extensions.txt", "item_lookup.txt"}
    
    for filepath in (Path(__file__).parent / "scraped_quests").rglob("*.txt"):
        if filepath.name not in excluded_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                file_updated = False
                updated_lines = []
                
                for line in lines:
                    # Skip comment lines and empty lines
                    if line.startswith('#') or not line.strip():
                        updated_lines.append(line)
                        continue
                    
                    # Split by tabs to get columns
                    parts = line.strip().split('\t')
                    if len(parts) >= 6:  # Ensure I have at least 6 columns
                        rewards_column = parts[5]  # Column 6 (0-indexed as 5)
                        
                        # Replace item extensions with names in the rewards column only
                        updated_rewards = rewards_column
                        for item_extension, item_name in item_mapping.items():
                            # Only replace if the item has a real name (not "Unknown Item")
                            if item_name != "Unknown Item":
                                updated_rewards = updated_rewards.replace(item_extension, item_name)
                        
                        # Update the rewards column
                        parts[5] = updated_rewards
                        
                        # Reconstruct the line
                        updated_line = '\t'.join(parts) + '\n'
                        updated_lines.append(updated_line)
                        
                        if updated_rewards != rewards_column:
                            file_updated = True
                    else:
                        # Keep lines that don't have enough columns unchanged
                        updated_lines.append(line)
                
                if file_updated:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.writelines(updated_lines)
                    replacements_made += 1
                    print(f"Updated {filepath}")
                
                quest_files_processed += 1
                
            except Exception as e:
                print(f"Error processing {filepath}: {e}")
    
    print(f"Processed {quest_files_processed} quest files")
    print(f"Made replacements in {replacements_made} files")

def get_category_from_extension(extension):
    """Determine category and subcategory from extension"""
    # Main category mapping
    category_mapping = {
        "0": "Eastern Kingdoms",
        "1": "Kalimdor", 
        "2": "Dungeons",
        "3": "Raids",
        "4": "Classes",
        "5": "Professions",
        "6": "Battlegrounds",
        "7": "Miscellaneous",
        "9": "World Events"
    }
    
    # Extract main category number and full extension
    if "=" in extension:
        parts = extension.split("=")[1]
        main_cat = parts.split(".")[0]
        category = category_mapping.get(main_cat, "Unknown")
        
        # Use the actual extension as subcategory for now
        # This will create files like "quests_0_1.txt" instead of hardcoded names
        subcategory = f"quests_{parts.replace('.', '_')}"
        
        return category, subcategory
    
    return "Unknown", "Unknown"

def scrape_quest_data(driver):
    """Scrape quest data from all extensions"""
    extensions_file = Path(__file__).parent / "scraped_quests" / "quest_extensions.txt"
    if not extensions_file.exists():
        print("Quest extensions file not found.")
        return
    
    # Parse extensions from file
    with open(extensions_file, 'r', encoding='utf-8') as f:
        extensions = [{'extension': parts[0].strip(), 
                      'category_name': parts[1].strip() if len(parts) > 1 else f"Category_{parts[0].replace('?quests=', '').replace('.', '_')}"}
                     for line in f if line.strip().startswith("/?quests=")
                     and len(parts := line.strip().split('\t')) >= 1]
    
    print(f"Found {len(extensions)} quest extensions to process")
    
    for i, ext_data in enumerate(extensions, 1):
        extension, category_name = ext_data['extension'], ext_data['category_name']
        main_category = get_category_from_extension(extension)[0]
        
        print(f"\n{i}/{len(extensions)}: Processing {extension} ({category_name})")
        print(f"Main Category: {main_category}, Subcategory: {category_name}")
        
        # Check if file is fresh
        filename = category_name.replace(" ", "_").replace("/", "_").replace("\\", "_") + ".txt"
        filepath = Path(__file__).parent / "scraped_quests" / main_category / filename
        
        if check_file_freshness(filepath, days=30):
            print(f"Quest data file is fresh, skipping...")
            continue
        
        # Navigate and handle consent
        driver.get(f"https://classicdb.ch{extension}")
        time.sleep(2)
        
        try:
            consent_iframe = driver.find_element(By.CSS_SELECTOR, "iframe[src*='privacy-mgmt.com']")
            driver.switch_to.frame(consent_iframe)
            driver.find_element(By.CSS_SELECTOR, "button[title='Accept'][aria-label='Accept']").click()
            driver.switch_to.default_content()
            time.sleep(1)
            print("Consent popup clicked")
        except:
            pass
        
        # Scrape and save
        quests = scrape_quest_page(driver, extension, main_category)
        save_quests_to_file(quests or [], main_category, category_name)
        
        if not quests:
            print(f"No quests found for {extension}")

def save_quest_extensions(quest_groups):
    """Save quest extensions to a file, grouped by first-level category"""
    # Create scraped_quests directory if it doesn't exist
    output_dir = Path(__file__).parent / "scraped_quests"
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / "quest_extensions.txt"
    
    total_extensions = sum(len(extensions) for extensions in quest_groups.values())
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"# Quest Extensions from classicdb.ch\n")
        f.write(f"# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Total groups found: {len(quest_groups)}\n")
        f.write(f"# Total extensions found: {total_extensions}\n\n")
        
        # Sort groups by their numeric value
        sorted_groups = sorted(quest_groups.keys(), key=lambda x: float(x) if x.replace('.', '').replace('-', '').isdigit() else x)
        
        for group in sorted_groups:
            extensions = quest_groups[group]
            f.write(f"## Group: ?quests={group} ({len(extensions)} extensions)\n")
            
            # Sort extensions within each group by extension
            sorted_extensions = sorted(extensions, key=lambda x: x['extension'])
            for ext_data in sorted_extensions:
                f.write(f"  {ext_data['extension']}\t{ext_data['category_name']}\n")
            
            f.write("\n")
    
    print(f"Saved {len(quest_groups)} quest groups with {total_extensions} total extensions to {output_file}")

def main():
    """Main function to scrape quest categories"""
    print("Scraping quest categories from classicdb.ch...")
    
    try:
        driver = setup_driver()
        driver.get("https://classicdb.ch/?quests")
        time.sleep(3)  # Wait for page to load
        
        # Handle consent popup if present
        try:
            # Find the consent iframe
            consent_iframe = driver.find_element(By.CSS_SELECTOR, "iframe[src*='privacy-mgmt.com']")
            if consent_iframe:
                print("Found consent popup...")
                # Switch to the iframe
                driver.switch_to.frame(consent_iframe)
                
                # Find and click the Accept button
                accept_button = driver.find_element(By.CSS_SELECTOR, "button[title='Accept'][aria-label='Accept']")
                accept_button.click()
                print("Clicked Accept button")
                
                # Switch back to main content
                driver.switch_to.default_content()
                time.sleep(1)
                print("Popup handled successfully")
        except Exception as e:
            print(f"Error handling consent popup: {e}")
        
        # Check if quest_extensions.txt is fresh (less than 30 days old)
        quest_file = Path(__file__).parent / "scraped_quests" / "quest_extensions.txt"
        is_fresh = check_file_freshness(quest_file, days=30)
        if is_fresh:
            print("Quest extensions file is fresh (less than 30 days old)")
            print("Using existing quest extensions data")
            
            # Skip quest category scraping and go straight to quest data scraping
            scrape_quest_data(driver)
            
            # Always run item lookup and replacement based on what was processed
            create_item_lookup_file(driver)
            
            replace_item_extensions_with_names()
            
        else:
            print("Quest extensions file is old or missing - will scrape new extensions")
            
            # Find quest categories
            quest_groups = find_quest_categories(driver)
            
            if quest_groups:
                # Save the extensions
                save_quest_extensions(quest_groups)
                
                # Display summary
                total_extensions = sum(len(extensions) for extensions in quest_groups.values())
                print(f"Total quest groups found: {len(quest_groups)}")
                print(f"Total quest extensions found: {total_extensions}")
                sorted_groups = sorted(quest_groups.keys(), key=lambda x: float(x) if x.replace('.', '').replace('-', '').isdigit() else x)
                for group in sorted_groups:
                    extensions = quest_groups[group]
                
                # Now scrape quest data from all extensions
                scrape_quest_data(driver)
                
                # Always run item lookup and replacement based on what was processed
                create_item_lookup_file(driver)
                
                replace_item_extensions_with_names()
                
            else:
                print("No quest extensions found")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'driver' in locals():
            driver.quit()
            print("WebDriver closed")
    
    # Run comment scraping after quest scraping is complete
    print("Starting comment scraping...")
    scrape_comments.main()

if __name__ == "__main__":
    main()
