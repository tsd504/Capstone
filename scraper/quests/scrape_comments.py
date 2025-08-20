import requests
from bs4 import BeautifulSoup
import time
import re
from datetime import datetime, timedelta
from pathlib import Path

def clean_text_for_csv(text):
    """Clean text to be safe for CSV format"""
    if not text:
        return "N/A"
    
    # Replace line breaks and multiple spaces with single spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Remove or replace characters that could break CSV
    text = text.replace('\t', ' ')  # Replace tabs with spaces
    text = text.replace('\n', ' ')  # Replace newlines with spaces
    text = text.replace('\r', ' ')  # Replace carriage returns with spaces
    text = text.replace('"', "'")   # Replace quotes with single quotes
    text = text.replace('#', '')    # Remove hash symbols
    
    # Strip extra whitespace
    text = text.strip()
    
    return text if text else "N/A"

def get_comment_scrape_timestamp(file_path):
    """Get the timestamp when comments were last scraped"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line in lines:
            if line.startswith('# Comment scrape timestamp:'):
                timestamp_str = line.replace('# Comment scrape timestamp:', '').strip()
                try:
                    return datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    return None
        return None
    except:
        return None



def should_rescrape_comments(file_path, max_age_hours=720):
    """Check if comments should be re-scraped based on age"""
    timestamp = get_comment_scrape_timestamp(file_path)
    if timestamp is None:
        return True  # No timestamp found, should scrape
    
    age = datetime.now() - timestamp
    return age > timedelta(hours=max_age_hours)

def scrape_quest_details(quest_extension):
    """Scrape quest details from classicdb.ch"""
    url = f"https://classicdb.ch{quest_extension}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 1. Find Instructions (text content from div class="text" after H1, before other headers)
        instructions = "N/A"
        
        # Look for the main content area
        main_content = soup.find('div', class_='text')
        if main_content:
            # Find the H1 quest title
            h1_title = main_content.find('h1')
            if h1_title:
                # Get all text content after the H1 until we hit a header tag
                instruction_text = ""
                
                # Find the position of the H1 within main_content
                h1_index = None
                for i, element in enumerate(main_content.children):
                    if element == h1_title:
                        h1_index = i
                        break
                
                if h1_index is not None:
                    # Start collecting text from the element AFTER the H1
                    for i, element in enumerate(main_content.children):
                        if i > h1_index:  # Only process elements after the H1
                            if element.name in ['h2', 'h3', 'h4', 'h5', 'h6']:
                                # Stop when we hit a section header
                                break
                            elif element.name is None:
                                # This is a text node
                                text = element.strip()
                                if text:
                                    instruction_text += text + " "
                            elif element.name in ['p', 'div', 'ul', 'li'] and not element.get('class'):
                                # For paragraphs, divs, and list items without specific classes
                                text = element.get_text(separator=' ', strip=True)
                                if text and len(text) > 5:
                                    instruction_text += text + " "
                            elif element.name == 'a':
                                # Handle standalone links
                                text = element.get_text().strip()
                                if text:
                                    instruction_text += text + " "
                            elif element.name == 'table' and element.get('class') and 'iconlist' in element.get('class'):
                                # Handle iconlist tables - process each cell to get links + text nodes
                                for td in element.find_all('td'):
                                    # Get all text content within this cell (links + text nodes)
                                    cell_text = td.get_text(separator=' ', strip=True)
                                    if cell_text and len(cell_text) > 2:  # Filter out very short text
                                        instruction_text += cell_text + " "
            
            # No fallback logic - if we didn't find text between H1 and next header, that's it
            
            # Clean up the instruction text
            if instruction_text:
                instruction_text = instruction_text.strip()
                # Remove "null " prefix if it appears at the beginning
                if instruction_text.startswith('null '):
                    instruction_text = instruction_text[5:].strip()
                
                instructions = clean_text_for_csv(instruction_text)
                
                if not instructions:
                    instructions = "N/A"
            else:
                instructions = "N/A"
        
        # 2. Find Progress (div id="progress" .text)
        progress = "N/A"
        progress_div = soup.find('div', id='progress')
        if progress_div:
            progress = clean_text_for_csv(progress_div.get_text())
        
        # 3. Find Start location (in infobox table)
        start_location = "N/A"
        infobox = soup.find('table', class_='infobox')
        if infobox:
            # Look for Start: text followed by a link
            start_text = infobox.find(string=re.compile(r'Start:'))
            if start_text:
                start_link = start_text.find_next('a')
                if start_link:
                    start_location = clean_text_for_csv(start_link.get_text())
        
        # 4. Find End location (in infobox table)
        end_location = "N/A"
        if infobox:
            # Look for End: text followed by a link
            end_text = infobox.find(string=re.compile(r'End:'))
            if end_text:
                end_link = end_text.find_next('a')
                if end_link:
                    end_location = clean_text_for_csv(end_link.get_text())
        
        # 5. Find top 5 comments with upvotes > 0
        comments = ["N/A"] * 5
        
        # Look for comments in JavaScript data
        script_tags = soup.find_all('script')
        for script in script_tags:
            if script.string and 'wh_comments' in script.string:
                # Extract comments from JavaScript
                comment_match = re.search(r'wh_comments\s*=\s*(\[.*?\]);', script.string, re.DOTALL)
                if comment_match:
                    try:
                        import json
                        comment_data = json.loads(comment_match.group(1))
                        
                        # Filter comments with positive ratings
                        valid_comments = []
                        for comment in comment_data:
                            if 'rating' in comment and comment['rating'] > 0:
                                body = comment.get('body', '')
                                if body:
                                    # Clean comment text for CSV
                                    clean_body = clean_text_for_csv(body)
                                    valid_comments.append((comment['rating'], clean_body))
                        
                        # Sort by rating (descending) and take top 5
                        valid_comments.sort(key=lambda x: x[0], reverse=True)
                        for i, (rating, comment_text) in enumerate(valid_comments[:5]):
                            comments[i] = comment_text
                        break
                    except:
                        pass
        
        return instructions, progress, start_location, end_location, comments
        
    except Exception as e:
        print(f"Error scraping {quest_extension}: {e}")
        return "N/A", "N/A", "N/A", "N/A", ["N/A"] * 5

def update_quest_file(file_path, progress_callback=None):
    """Update quest file with additional columns"""
    # Check if we need to scrape comments
    if not should_rescrape_comments(file_path):
        return
    
    # Read existing content
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find header line and check if new columns already exist
    header_line = None
    for i, line in enumerate(lines):
        if line.startswith('Quest Extension\t'):
            header_line = i
            break
    
    if header_line is None:
        print("Could not find header line")
        return
    
    # Check if new columns already exist
    header_content = lines[header_line].strip()
    new_headers = ['Instructions', 'Progress', 'Start', 'End', 'Comment1', 'Comment2', 'Comment3', 'Comment4', 'Comment5']
    
    # Check if any of the new headers already exist in the header
    columns_exist = any(header in header_content for header in new_headers)
    
    if columns_exist:
        print("New columns already exist in the file. Updating existing data...")
        
        # Check if we need to rename Description to Instructions
        if 'Description' in header_content and 'Instructions' not in header_content:
            print("Renaming 'Description' column to 'Instructions'...")
            header_content = header_content.replace('Description', 'Instructions')
            lines[header_line] = header_content + '\n'
        
        # Find the column positions for existing data
        header_parts = header_content.split('\t')
        desc_col = None
        progress_col = None
        start_col = None
        end_col = None
        comment_cols = []
        
        for i, col in enumerate(header_parts):
            if col == 'Instructions':
                desc_col = i
            elif col == 'Progress':
                progress_col = i
            elif col == 'Start':
                start_col = i
            elif col == 'End':
                end_col = i
            elif col.startswith('Comment'):
                comment_cols.append(i)
        
        
    
        # Process each quest line (skip header and comment lines)
        quest_lines = []
        for i in range(header_line + 1, len(lines)):
            line = lines[i].strip()
            if line and not line.startswith('#') and '\t' in line:
                quest_lines.append((i, line))
        
        total_quests = len(quest_lines)
        
        for idx, (line_index, line) in enumerate(quest_lines, 1):
            # Extract quest extension
            quest_extension = line.split('\t')[0]
            
            # Update progress via callback if provided
            if progress_callback:
                progress_callback(f"Processing quest {idx}/{total_quests}: {quest_extension}")
            
            # Scrape quest details
            instructions, progress, start, end, comments = scrape_quest_details(quest_extension)
            
            # Update existing columns with new data
            line_parts = line.split('\t')
            
            # Ensure line_parts has enough columns
            max_col = 0
            for col in [desc_col, progress_col, start_col, end_col] + comment_cols:
                if col is not None:
                    max_col = max(max_col, col)
            
            while len(line_parts) < max_col + 1:
                line_parts.append('N/A')
            
            # Update existing columns
            if desc_col is not None:
                line_parts[desc_col] = instructions
            if progress_col is not None:
                line_parts[progress_col] = progress
            if start_col is not None:
                line_parts[start_col] = start
            if end_col is not None:
                line_parts[end_col] = end
            
            # Update comment columns
            for j, comment_col in enumerate(comment_cols[:5]):
                if j < len(comments):
                    line_parts[comment_col] = comments[j]
            
            lines[line_index] = '\t'.join(line_parts) + '\n'
            
            # Small delay to be respectful to the server
            time.sleep(0.5)
    else:
        # Add new column headers
        lines[header_line] = lines[header_line].strip() + '\t' + '\t'.join(new_headers) + '\n'
        
        # Process each quest line (skip header and comment lines)
        quest_lines = []
        for i in range(header_line + 1, len(lines)):
            line = lines[i].strip()
            if line and not line.startswith('#') and '\t' in line:
                quest_lines.append((i, line))
        
        total_quests = len(quest_lines)
        
        for idx, (line_index, line) in enumerate(quest_lines, 1):
            # Extract quest extension
            quest_extension = line.split('\t')[0]
            
            # Update progress via callback if provided
            if progress_callback:
                progress_callback(f"Processing quest {idx}/{total_quests}: {quest_extension}")
            
            # Scrape quest details
            instructions, progress, start, end, comments = scrape_quest_details(quest_extension)
            
            # Append new data to the line
            new_data = [instructions, progress, start, end] + comments
            lines[line_index] = line + '\t' + '\t'.join(new_data) + '\n'
            
            # Small delay to be respectful to the server
            time.sleep(0.5)

    

    # Add timestamp BEFORE writing
    insert_index = None
    for i, line in enumerate(lines):
        if line.startswith('# Total quests:'):
            insert_index = i + 1
            break

    if insert_index is not None:
        # Check if timestamp already exists
        timestamp_exists = False
        for i, line in enumerate(lines):
            if line.startswith('# Comment scrape timestamp:'):
                lines[i] = f"# Comment scrape timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                timestamp_exists = True
                break
        
        if not timestamp_exists:
            lines.insert(insert_index, f"# Comment scrape timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Write updated content back to file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)



def find_all_quest_files():
    """Find all quest files in the scraped_quests directory"""
    quest_files = []
    scraped_quests_dir = Path(__file__).parent / "scraped_quests"
    
    if not scraped_quests_dir.exists():
        print(f"Directory not found: {scraped_quests_dir}")
        return []
    
    # Walk through all subdirectories
    for file_path in scraped_quests_dir.rglob('*.txt'):
        if file_path.name not in ['class_links.txt', 'raid_links.txt', 'item_lookup.txt', 'quest_extensions.txt']:
            quest_files.append(str(file_path))
    
    return quest_files

def main():
    """Main function to update all quest files"""
    quest_files = find_all_quest_files()
    
    if not quest_files:
        print("No quest files found!")
        return
    
    print(f"Found {len(quest_files)} quest files to process...")
    
    # Process each quest file
    for i, file_path in enumerate(quest_files, 1):
        # Check if we need to scrape
        if should_rescrape_comments(file_path):
            try:
                # Show file progress and quest progress on same line
                print(f"Processing file {i}/{len(quest_files)}: {Path(file_path).name} - Scraping comments...", end='\r')
                
                # Get quest count first
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                quest_count = 0
                for line in lines:
                    if line.strip() and not line.startswith('#') and '\t' in line:
                        quest_count += 1
                
                # Update the line to show quest count
                print(f"Processing file {i}/{len(quest_files)}: {Path(file_path).name} - Found {quest_count} quests to process...", end='\r')
                
                # Create progress callback to update the same line
                def update_progress(message):
                    print(f"Processing file {i}/{len(quest_files)}: {Path(file_path).name} - {message}", end='\r')
                
                update_quest_file(file_path, progress_callback=update_progress)
                
            except Exception as e:
                # Show error on same line
                print(f"❌ Error in file {i}/{len(quest_files)}: {Path(file_path).name} - {e}{' ' * 50}")
                continue
        else:
            # Show skipped status on same line
            print(f"⏭️  Skipped file {i}/{len(quest_files)}: {Path(file_path).name} (fresh){' ' * 50}")
    
    print(f"\n{'='*60}")
    print("All quest files processed!")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
