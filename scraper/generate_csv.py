import csv
from pathlib import Path

def generate_item_csv():
    """Combine all item data"""
    raid_phase = { # Some prompts may refer to raid phases, so I need to add the phase number to the data
        'Blackwing Lair': 4, 'Molten Core': 2, 'Onyxia': 2,
        'Ruins of Ahn\'Qiraj': 5, 'Temple of Ahn\'Qiraj': 5, 'Zul\'Gurub': 4
    }
    
    all_data = []
    for raid_dir in Path('items/structured_items').iterdir(): # Raid folders
        if not raid_dir.is_dir(): continue # Skip if not a directory
        for class_dir in raid_dir.iterdir(): # Class folders
            if not class_dir.is_dir(): continue # Skip if not a directory
            for spec_file in class_dir.glob('*.txt'): # Only txt files (spec files)
                try:
                    with open(spec_file, 'r', encoding='utf-8') as f: # Read the spec file
                        lines = [line.strip() for line in f if line.strip() and not line.startswith('#')] # Skip empty lines and comments
                    
                    # Data has a header, so I skip the first line
                    for line in lines[1:]:
                        # Rows are tab separated + I add the raid name, phase, class, and spec
                        row = line.split('\t') + [raid_dir.name, raid_phase.get(raid_dir.name, 'Unknown'), 
                                                  class_dir.name, spec_file.stem] # Folder names & Truncated file name
                        all_data.append(row)
                except Exception as e:
                    print(f"Error with {spec_file}: {e}")
    
    if all_data: # If all_data is not empty
        headers = ['Rank', 'Name', 'Guild', 'Faction', 'DPS', 'Size', 'Date', 'Duration',
                  'Head', 'Neck', 'Shoulder', 'Chest', 'Waist', 'Legs', 'Feet', 'Wrist',
                  'Hands', 'Ring1', 'Ring2', 'Trinket1', 'Trinket2', 'Back', 'Weapon1',
                  'Weapon2', 'Ranged', 'Raid', 'Phase', 'Class', 'Specialisation']
        
        with open('items_combined.csv', 'w', newline='', encoding='utf-8-sig') as f: #utf-8-sig is an encoding for special characters
            data_to_write = [headers] + all_data # Combine the headers and the data
            csv.writer(f).writerows(data_to_write) # Write the data to the csv file
        print(f"items_combined.csv created with {len(all_data)} rows")
        return 'items_combined.csv'
    return None

def generate_quest_csv():
    """Combine all quest data"""
    all_data = []
    for cat_dir in Path('quests/scraped_quests').iterdir(): # Category folders
        if not cat_dir.is_dir(): continue # Skip if not a directory
        for file in cat_dir.glob('*.txt'): # Only txt files (quest files)
            try:
                with open(file, 'r', encoding='utf-8') as f: # Read the quest file
                    lines = [line.strip() for line in f if line.strip() and not line.startswith('#')] # Skip empty lines and comments
                
                # Data has a header, so we skip the first line
                for line in lines[1:]:
                    # Rows are tab separated + We add the category and quest name
                    row = line.split('\t') + [cat_dir.name, file.stem.replace('_', ' ')] # Folder names & Truncated file name
                    all_data.append(row)
            except Exception as e:
                print(f"Error with {file}: {e}")
    
    if all_data: # If all_data is not empty
        headers = ['Quest Extension', 'Name', 'Level', 'Required Level', 'Faction', 'Rewards',
                  'Category', 'Instructions', 'Progress', 'Start', 'End', 'Comment1',
                  'Comment2', 'Comment3', 'Comment4', 'Comment5', 'Type', 'Sub-Type']
        
        with open('quests_combined.csv', 'w', newline='', encoding='utf-8-sig') as f: #utf-8-sig is an encoding for special characters
            data_to_write = [headers] + all_data # Combine the headers and the data
            csv.writer(f).writerows(data_to_write) # Write the data to the csv file
        print(f"quests_combined.csv created with {len(all_data)} rows")
        return 'quests_combined.csv'
    return None

if __name__ == "__main__":
    print("Generating item CSV...")
    generate_item_csv()
    print("Generating quest CSV...")
    generate_quest_csv()
    print("Done!")
