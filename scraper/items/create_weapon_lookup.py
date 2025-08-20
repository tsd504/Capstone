import re
import requests
import time
from bs4 import BeautifulSoup
from pathlib import Path

def extract_unique_weapon_ids():
    """Extract all unique weapon IDs from structured_items data"""
    weapon_ids = set()
    script_dir = Path(__file__).parent
    structured_dir = script_dir / "structured_items"
    
    for file_path in structured_dir.rglob('*.txt'): # Recursive glob
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f.readlines()[1:]:  # Skip header
                    if line.strip():
                        parts = line.strip().split('\t')
                        if len(parts) >= 25:
                            # Process all three weapon columns
                            weapon1, weapon2, ranged = parts[22], parts[23], parts[24]
                            
                            # Extract weapon IDs from all three columns
                            for weapons in [weapon1, weapon2, ranged]:
                                if weapons and weapons != 'N/A':
                                    weapon_ids.update(re.findall(r'\((\d+)\)', weapons))
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
    
    return sorted(list(weapon_ids))

def categorise_weapon(item_id):
    """Look up weapon on classicdb.ch and categorise it based on HTML structure"""
    try:
        response = requests.get(f"https://classicdb.ch/?item={item_id}", timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')

        equipment_slot = None
        
        # Find all td elements and look for equipment slot information
        # Old code looked for the words in any text, but miscategorised when item descriptions contained certain words
        for td in soup.find_all('td'):
            text = td.get_text().strip().lower()
            if text in ['main hand', 'one-hand', 'ranged', 'relic', 'two-hand', 'held in off-hand', 'off hand']:
                equipment_slot = text
                break
        
        # Categorise based on equipment slot
        if equipment_slot:
            if equipment_slot in ['ranged', 'relic']:
                return 'ranged'
            elif equipment_slot in ['held in off-hand', 'off hand']:
                return 'off-hand'
            elif equipment_slot in ['main hand', 'two-hand']:
                return 'main-hand-only'
            elif equipment_slot == 'one-hand':
                return 'one-hand'
        
        return 'unknown'
    except Exception as e:
        print(f"Error looking up item {item_id}: {e}")
        return 'error'

def load_existing_categorisations(lookup_file):
    """Load existing weapon categorisations from file"""
    existing = {}
    if lookup_file.exists():
        print("Loading existing weapon categorisations...")
        with open(lookup_file, 'r', encoding='utf-8') as f:
            for line in f.readlines()[1:]:  # Skip header
                if line.strip():
                    parts = line.strip().split('\t')
                    if len(parts) >= 2:
                        existing[parts[0]] = parts[1]
        print(f"Loaded {len(existing)} existing categorisations")
    return existing

def save_categorisations(lookup_file, all_categorisations):
    """Save all categorisations to file"""
    with open(lookup_file, 'w', encoding='utf-8') as f:
        f.write("Item_ID\tWeapon_Type\n")
        for item_id in sorted(all_categorisations.keys()):
            f.write(f"{item_id}\t{all_categorisations[item_id]}\n")

def create_weapon_lookup():
    """Create weapon lookup file with categorisations"""
    print("Extracting unique weapon IDs...")
    weapon_ids = extract_unique_weapon_ids()
    print(f"Found {len(weapon_ids)} unique weapon IDs")
    
    script_dir = Path(__file__).parent
    lookup_file = script_dir / "scraped_items" / "weapon_lookup.txt"
    existing_categorisations = load_existing_categorisations(lookup_file)
    
    # Filter to weapons that need categorisation
    weapons_to_categorise = [item_id for item_id in weapon_ids if item_id not in existing_categorisations or existing_categorisations[item_id] == 'unknown']
    
    print(f"Need to categorise {len(weapons_to_categorise)} weapons...")
    
    if not weapons_to_categorise:
        print("All weapons already categorised!")
        return
    
    # Create/update weapon lookup file
    lookup_file.parent.mkdir(parents=True, exist_ok=True)
    all_categorisations = existing_categorisations.copy()
    categorised_weapons = 0
    
    # Categorise new weapons
    for i, item_id in enumerate(weapons_to_categorise, 1):
        print(f"Processing {i}/{len(weapons_to_categorise)}: Item {item_id}")
        weapon_type = categorise_weapon(item_id)
        all_categorisations[item_id] = weapon_type
        
        if weapon_type != 'error':
            categorised_weapons += 1
        
        # Save progress after each weapon
        save_categorisations(lookup_file, all_categorisations)
        print(f"  → Saved as {weapon_type}")
        time.sleep(0.5)  # Be respectful to server
    
    print(f"\nWeapon lookup complete!")
    print(f"Total weapons: {len(weapon_ids)}")
    print(f"Successfully categorised: {categorised_weapons}")
    print(f"Lookup file saved to: {lookup_file}")

if __name__ == "__main__":
    create_weapon_lookup()
