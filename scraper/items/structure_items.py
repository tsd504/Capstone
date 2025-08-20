import re
import html
from bs4 import BeautifulSoup
from pathlib import Path

# NOTE: ISSUES SOLVED BY THIS FILE
# A player could have 15-19 items equipped, some items are cosmetic and should not be recorded.
# Weapons are placed in the first available slot by default, so I need to classify items into slots. This is done in create_weapon_lookup.py.
# weapon_lookup.txt is used to lookup weapons and find their type. Allowing me to place weapons in the correct slot.
# HTML content is parsed using BeautifulSoup, allowing me to extract the data I need.

COSMETIC_ITEMS = {
    "Rugged Trapper's Shirt", "Common White Shirt", "Orange Mageweave Shirt", 
    "Formal White Shirt", "Stylish Black Shirt", "Pink Mageweave Shirt", 
    "Primitive Mantle", "Brawler's Harness", "Sawbones Shirt", "Thug Shirt", 
    "Tuxedo Shirt", "Neophyte's Shirt", "Rich Purple Silk Shirt", "Trapper's Shirt", 
    "Lavender Mageweave Shirt", "Orange Martial Shirt", "Gray Woolen Shirt", 
    "Stylish Green Shirt", "Dark Silk Shirt", "Master Builder's Shirt", 
    "Common Brown Shirt", "Red Linen Shirt", "Stylish Red Shirt", "Footpad's Shirt", 
    "Bright Yellow Shirt", "Blue Linen Shirt", "Acolyte's Shirt", 
    "White Swashbuckler's Shirt", "Green Linen Shirt", "Recruit's Shirt", 
    "Bold Yellow Shirt", "Squire's Shirt", "Brown Linen Shirt", "White Tuxedo Shirt", 
    "Deckhand's Shirt", "Black Swashbuckler's Shirt", "Fine Cloth Shirt", 
    "Green Holiday Shirt", "Apprentice's Shirt", "White Linen Shirt", 
    "Stylish Blue Shirt", "Captain Sanders' Shirt", "Red Swashbuckler's Shirt", 
    "Sleeveless T-Shirt", "Common Gray Shirt"
}

weapon_lookup_cache = {}

def load_weapon_lookup():
    """Load existing weapon lookup data from weapon_lookup.txt"""
    global weapon_lookup_cache
    
    if weapon_lookup_cache:  # Is already loaded
        return
    
    lookup_file = Path(__file__).parent / "scraped_items" / "weapon_lookup.txt" # Path relative to files location, not working directory
    # Loads existing weapons that have already been categorised
    if lookup_file.exists():
        try:
            with open(lookup_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if len(lines) > 1:  # Data exists
                    for line in lines[1:]: # Skip header row
                        if line.strip(): # Data isn't just spaces
                            parts = line.strip().split('\t') # split by tabs
                            if len(parts) >= 2: # Weapon already has type
                                item_id = parts[0]
                                weapon_type = parts[1]
                                weapon_lookup_cache[item_id] = weapon_type
            print(f"Loaded {len(weapon_lookup_cache)} weapons")
        except Exception as e:
            print(f"Error with {lookup_file}: {e}")
    else:
        print("Warning: weapon_lookup.txt not found. Weapons will be marked as 'unknown'") # Unknown weapons get filled into the first available item slot, like the default
        print("Run create_weapon_lookup.py first and try again")

def get_weapon_type(item_id):
    """Get weapon type for an item ID"""
    if not weapon_lookup_cache: # If cache is empty then populate it
        load_weapon_lookup()
    
    return weapon_lookup_cache.get(item_id, 'unknown') # Return type of item

def extract_player_data(html_content):
    """Extract structured player data from HTML content using BeautifulSoup"""
    players = []
    
    soup = BeautifulSoup(html_content, 'html.parser') # Parse the HTML content
    player_rows = soup.find_all('tr', id=lambda x: x and x.startswith('row-'))
    
    for i, row in enumerate(player_rows):
        try:
            player_id = row.get('id').replace('row-', '')
            
            name_cell = row.find('td', class_='main-table-name') # Extract the name of the player
            if not name_cell:
                continue
                
            name_link = name_cell.find('a', class_=lambda x: x and 'main-table-link' in x and 'main-table-player' in x)
            if not name_link:
                continue
                
            name = html.unescape(name_link.get_text(strip=True)) # Some text like ' is encoded so unescape it
            
            guild = "N/A" # Default values
            faction = "Unknown" # Default values
            
            guild_div = row.find('div', class_='players-table-guild-and-realm')
            if guild_div:
                guild_link = guild_div.find('a', class_='players-table-guild')
                if guild_link:
                    guild = html.unescape(guild_link.get_text(strip=True))
                    
                    guild_classes = guild_link.get('class', []) # 0 = Alliance, 1 = Horde, Default is Unknown
                    for cls in guild_classes:
                        if cls.startswith('faction-'):
                            faction_num = cls.split('-')[1]
                            if faction_num == "0":
                                faction = "Alliance"
                            elif faction_num == "1":
                                faction = "Horde"
                            break
            
            # Default values
            dps = "N/A"
            size = "N/A"
            date = "N/A"
            duration = "N/A"
            
            # Find cells by class
            dps_cell = row.find('td', class_=lambda x: x and 'players-table-dps' in x)
            if dps_cell:
                dps = dps_cell.get_text(strip=True)
            
            size_cell = row.find('td', class_=lambda x: x and 'players-table-size' in x)
            if size_cell:
                size = size_cell.get_text(strip=True)
            
            # In the HTML time related td's have a span with text I don't want, so decompose is needed to remove the spans
            date_cell = row.find('td', class_=lambda x: x and 'players-table-date' in x)
            if date_cell:
                # Remove hidden spans and get text
                for span in date_cell.find_all('span', style='display:none'):
                    span.decompose()
                date = date_cell.get_text(strip=True)
            
            # In the HTML time related td's have a span with text I don't want, so decompose is needed to remove the spans
            duration_cell = row.find('td', class_=lambda x: x and 'players-table-duration' in x)
            if duration_cell:
                # Remove hidden spans and get text
                for span in duration_cell.find_all('span', style='display:none'):
                    span.decompose()
                duration = duration_cell.get_text(strip=True)
            
            # Extract gear items from JavaScript data
            gear_items = extract_gear_items(player_id, html_content)
            
            players.append({
                'rank': i + 1,
                'name': name,
                'guild': guild,
                'faction': faction,
                'dps': dps,
                'size': size,
                'date': date,
                'duration': duration,
                'gear': gear_items
            })
            
        except Exception as e:
            print(f"Error processing player {player_id}: {e}")
            continue
    
    return players

def extract_gear_items(player_id, html_content):
    """Extract gear items from JavaScript gear data, excluding cosmetics"""
    # Find the JavaScript gear data for this player
    gear_pattern = rf'talentsAndGear\["row-{player_id}"\]\.gear\.push\(\{{[^}}]*name:\s*"([^"]+)"[^}}]*id:\s*(\d+)'
    item_matches = re.findall(gear_pattern, html_content, re.DOTALL) # re.DOTALL allows . to match newlines
    
    # Filter out cosmetic items and decode HTML entities
    non_cosmetic_items = []
    for item_name, item_id in item_matches:
        item_name = html.unescape(item_name)
        if item_name not in COSMETIC_ITEMS:
            non_cosmetic_items.append((item_name, item_id))
    
    # Classify items into slots
    gear_slots = classify_items_into_slots(non_cosmetic_items)
    
    return gear_slots

def classify_items_into_slots(items):
    """Classify items into their appropriate gear slots based on equipment type"""
    # Without this code weapons were being placed in the first available slot since not everyone has 3 weapons equipped

    # Default values
    slots = {
        'Head': 'N/A', 'Neck': 'N/A', 'Shoulder': 'N/A', 'Chest': 'N/A',
        'Waist': 'N/A', 'Legs': 'N/A', 'Feet': 'N/A', 'Wrist': 'N/A',
        'Hands': 'N/A', 'Ring1': 'N/A', 'Ring2': 'N/A', 'Trinket1': 'N/A',
        'Trinket2': 'N/A', 'Back': 'N/A', 'Weapon1': 'N/A', 'Weapon2': 'N/A', 'Ranged': 'N/A'
    }
    
    if not items:
        return slots
    
    total_items = len(items)
    
    # Always assign items 1-13 to Head through Trinket2
    for i, (item_name, item_id) in enumerate(items[:13]):
        if i == 0: slots['Head'] = f"{item_name} ({item_id})"
        elif i == 1: slots['Neck'] = f"{item_name} ({item_id})"
        elif i == 2: slots['Shoulder'] = f"{item_name} ({item_id})"
        elif i == 3: slots['Chest'] = f"{item_name} ({item_id})"
        elif i == 4: slots['Waist'] = f"{item_name} ({item_id})"
        elif i == 5: slots['Legs'] = f"{item_name} ({item_id})"
        elif i == 6: slots['Feet'] = f"{item_name} ({item_id})"
        elif i == 7: slots['Wrist'] = f"{item_name} ({item_id})"
        elif i == 8: slots['Hands'] = f"{item_name} ({item_id})"
        elif i == 9: slots['Ring1'] = f"{item_name} ({item_id})"
        elif i == 10: slots['Ring2'] = f"{item_name} ({item_id})"
        elif i == 11: slots['Trinket1'] = f"{item_name} ({item_id})"
        elif i == 12: slots['Trinket2'] = f"{item_name} ({item_id})"
    
    # Handle Back slot (item 14) and Weapons (items 15+)
    if total_items >= 14:
        # Item 14 goes in Back slot
        slots['Back'] = f"{items[13][0]} ({items[13][1]})"
        
        # Process remaining items as weapons using weapon lookup
        if total_items >= 15:
            weapon_items = items[14:]
            for item_name, item_id in weapon_items:
                weapon_type = get_weapon_type(item_id)
                # Weapon type is known
                if weapon_type == 'main-hand-only': # Main hand weapon is always weapon1
                    slots['Weapon1'] = f"{item_name} ({item_id})"
                elif weapon_type == 'off-hand': # Off hand weapon is always weapon2
                    slots['Weapon2'] = f"{item_name} ({item_id})"
                elif weapon_type == 'ranged': # Ranged weapon is always ranged
                    slots['Ranged'] = f"{item_name} ({item_id})"
                elif weapon_type == 'one-hand': # One hand weapons are placed in first available slot
                    if slots['Weapon1'] == 'N/A':
                        slots['Weapon1'] = f"{item_name} ({item_id})"
                    elif slots['Weapon2'] == 'N/A':
                        slots['Weapon2'] = f"{item_name} ({item_id})"
                    else:
                        # Both slots filled, this shouldn't happen with the data I have
                        print(f"Warning: Both weapon slots filled for {item_name} ({item_id})")
                else: # Weapon type is unknown
                    # Unknown weapon type, place in first available slot
                    if slots['Weapon1'] == 'N/A':
                        slots['Weapon1'] = f"{item_name} ({item_id})"
                    elif slots['Weapon2'] == 'N/A':
                        slots['Weapon2'] = f"{item_name} ({item_id})"
                    else:
                        slots['Ranged'] = f"{item_name} ({item_id})"
    
    return slots

def save_structured_data(players, output_file):
    """Save structured player data to file"""
    Path(output_file).parent.mkdir(parents=True, exist_ok=True) # Create the directory if it doesn't exist
    
    with open(output_file, 'w', encoding='utf-8') as f:
        # Write header
        header = [
            'Rank', 'Name', 'Guild', 'Faction', 'DPS', 'Size', 'Date', 'Duration',
            'Head', 'Neck', 'Shoulder', 'Chest', 'Waist', 'Legs', 'Feet', 'Wrist',
            'Hands', 'Ring1', 'Ring2', 'Trinket1', 'Trinket2', 'Back', 'Weapon1', 'Weapon2', 'Ranged'
        ]
        f.write('\t'.join(header) + '\n') # Write headers separated by tabs
        
        # Write player data
        for player in players:
            row = [
                str(player['rank']),
                player['name'],
                player['guild'],
                player['faction'],
                player['dps'],
                player['size'],
                player['date'],
                player['duration']
            ]
            
            # Add gear slots
            gear = player['gear']
            row.extend([
                gear['Head'], gear['Neck'], gear['Shoulder'], gear['Chest'],
                gear['Waist'], gear['Legs'], gear['Feet'], gear['Wrist'],
                gear['Hands'], gear['Ring1'], gear['Ring2'], gear['Trinket1'],
                gear['Trinket2'], gear['Back'], gear['Weapon1'], gear['Weapon2'], gear['Ranged']
            ])
            
            f.write('\t'.join(row) + '\n')

def process_all_files():
    """Process all files in scraped_items and create structured versions"""
    script_dir = Path(__file__).parent
    scraped_dir = script_dir / "scraped_items"
    structured_dir = script_dir / "structured_items"
    
    structured_dir.mkdir(parents=True, exist_ok=True) # Create main structured directory
    
    total_files = 0
    processed_files = 0
    
    # Walk through all files in items/scraped_items
    for raid_dir in scraped_dir.iterdir():
        if not raid_dir.is_dir() or raid_dir.name in ['__pycache__']: # This skips the other files in the directory
            continue
            
        print(f"\nProcessing raid: {raid_dir.name}")
        
        # Create raid directory in items/structured_items
        structured_raid_path = structured_dir / raid_dir.name
        structured_raid_path.mkdir(parents=True, exist_ok=True)
        
        for class_dir in raid_dir.iterdir():
            if not class_dir.is_dir():
                continue
                
            # Create class directory
            structured_class_path = structured_raid_path / class_dir.name
            structured_class_path.mkdir(parents=True, exist_ok=True)
            
            for spec_file in class_dir.glob('*.txt'):
                total_files += 1
                structured_spec_path = structured_class_path / spec_file.name
                
                print(f"  Processing: {class_dir.name}/{spec_file.name}")
                
                try:
                    # Read HTML content
                    with open(spec_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Skip timestamp line and find the actual HTML content
                    lines = content.split('\n')
                    
                    # Find where the HTML table starts
                    for i, line in enumerate(lines):
                        if '<table' in line and 'class="summary-table' in line:
                            html_content = '\n'.join(lines[i:])
                            break
                    
                    # Extract player data
                    players = extract_player_data(html_content)
                    
                    if players:
                        # Save structured data
                        save_structured_data(players, structured_spec_path)
                        processed_files += 1
                        print(f"Processed {len(players)} players")
                    else:
                        print(f"No players found")
                
                except Exception as e:
                    print(f"Error processing {spec_file.name}: {e}")
                    continue

    print(f"  Total files: {total_files}")
    print(f"  Successfully processed: {processed_files}")
    print(f"  Failed: {total_files - processed_files}")

if __name__ == "__main__":
    process_all_files()
