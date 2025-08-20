import praw
import google.generativeai as genai
import csv
from datetime import datetime
import json
from pathlib import Path

# Load credentials from JSON file
credentials_path = Path(__file__).parent / 'reddit_credentials.json'
try:
    with open(credentials_path, 'r') as f:
        reddit_credentials = json.load(f)
    print("Loaded credentials from reddit_credentials.json")
except FileNotFoundError:
    print("Warning: reddit_credentials.json not found. Make sure it's in the same directory as this script.")
    exit(1)

# Configure Gemini
GEMINI_API_KEY = reddit_credentials["gemini_api_key"]
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-1.5-flash")

# PRAW with username/password authentication
reddit = praw.Reddit(
    client_id=reddit_credentials["client_id"],
    client_secret=reddit_credentials["client_secret"],
    username=reddit_credentials["username"],
    password=reddit_credentials["password"],
    user_agent="ClassicRAGBot/1.0 (by /u/Many-Emergency7458)"
)

print("PRAW authentication successful!")
print(f"Read-only: {reddit.read_only}")

def is_post_relevant(post_content):
    """Use Gemini to determine if a post can be answered with my data"""
    try:
        prompt = f"""

            You have data on:
            - Items worn by the top 100 players of each class and spec in Classic WoW in the following raids:
                * Molten Core (MC)
                * Onyxia (Ony)
                * Blackwing Lair (BWL)
                * Zul'Gurub (ZG)
                * Ruins of Ahn'Qiraj (AQ20)
                * Temple of Ahn'Qiraj (AQ40)
            Example 1: Rank: 1 || Name: Stuba || Guild: The Pond pug || Faction: Horde || DPS: 818.3 || Size: 40 || Date: Jun-14 || Duration: 42:41:00 || Head: Mish'undare, Circlet of the Mind Flayer (19375) || Neck: Choker of the Fire Lord (18814) || Shoulder: Cyclone Spaulders (18528) || Chest: Bloodvine Vest (19682) || Waist: Firemaw's Clutch (19400) || Legs: Bloodvine Leggings (19683) || Feet: Bloodvine Boots (19684) || Wrist: Master's Bracers (10248) || Hands: Bloodtinged Gloves (19929) || Ring1: Zanzil's Band (19905) || Ring2: Zanzil's Seal (19893) || Trinket1: Eye of the Beast (13968) || Trinket2: Zandalarian Hero Charm (19950) || Back: Cloak of Consumption (19857) || Weapon1: Staff of the Shadow Flame (19356) || Ranged: Idol of Rejuvenation (22398) || Raid: Blackwing Lair || Phase: 4 || Class: Druid || Specialisation: Balance
            Example 2: Rank: 54 || Name: 尛陸 || Guild: On Your Left || Faction: Alliance || DPS: 44.7 || Size: 35 || Date: May-10 || Duration: 01:01:12 || Head: Field Marshal's Lamellar Faceguard (16474) || Neck: Medallion of Grand Marshal Morris (13091) || Shoulder: Field Marshal's Lamellar Pauldrons (16476) || Chest: Field Marshal's Lamellar Chestplate (16473) || Waist: Lawbringer Belt (16858) || Legs: Marshal's Lamellar Legplates (16475) || Feet: Marshal's Lamellar Boots (16472) || Wrist: Judgment Bindings (16951) || Hands: Marshal's Lamellar Gloves (16471) || Ring1: Overlord's Onyx Band (19912) || Ring2: Myrmidon's Signet (2246) || Trinket1: Stormpike Insignia Rank 6 (17904) || Trinket2: Essence of the Pure Flame (18815) || Back: Hide of the Wild (18510) || Weapon1: Grand Marshal's Swiftblade (23456) || Weapon2: Grand Marshal's Aegis (18825) || Raid: Blackwing Lair || Phase: 4 || Class: Paladin || Specialisation: Holy

            - Data on almost all quests for Classic WoW
            Example 1: Quest Extension: /?quest=8227 || Name: Nat's Measuring Tape || Level: 60 Raid || Required Level: 58 || Faction: Both || Rewards: 650 XP || Category: Raids || Instructions: Return Nat's Measuring Tape to Nat Pagle in Dustwallow Marsh. Nat's Measuring Tape Provided Item: Nat's Measuring Tape || Progress: Hello there, <laddie/lassy>. You here to do some fishing? || Start: Battered Tackle Box || End: Nat Pagle || Comment1: After you turn this in, you can get mudskunk lures to summon Gahz'ranka in ZG. In addition to the lures you will need to catch 5 zulian mudskunks from muddy churning waters in ZG. I've noticed you need at least 380 fishing skill to catch them. I was able to catch with with 260 skill + aquadymamic fish attractor (+100 skill) + a the fishing pole that gives +25 to skill. || Comment2: Ok.Ppl this quest is need it to summon Gahz`Ranka, the 6th boss in Zul`Gurub.Wene u have Nat's Measuring Tape quest go in Dustwallow Marsh at Nat Pagle Npc(coord 58,60)and after u can buy from him Mudskunk Lure that must be loaded with 5xZulian Mudskunk fishs(u can get them only in Zul`Gurub waters) || Comment3: He's at 58,60. || Comment4: If you have fishing skill, you'll be able to talk to Nat Pagle about..y'know...the weather and fishing, and big freakin' monsters that live in the water. And he'll tell you how to summon such big freakin' monsters ([url=/npc=15114]Gahz'ranka[/url]) and sells [item=19974] which is used. || Comment5: Can be picked up solo by any level 70, did it as a warrior. With a bit of coordination you should be able to get to Pagle's Point (shown on various map addons as the spawn location of Gahz'Ranka) without aggroing anything. I went over the first bridge, then north down into the water and across, over the 2nd bridge, over the path south of Arlokk's temple, and shortly after south to Pagle's Pointe where I was able to pick up the measuring tape from the battered tackle box. If you manage to aggro a Frenzy while in the water, you should normally go out of combat again shortly after getting out of the water. || Type: Raids || Sub-Type: Zul'Gurub

            Data is relevant for Era / Fresh / Anniversary versions of the game and not others.
            
            Can this Reddit post be answered using this data? 

            Post: {post_content}

            Respond with only: YES or NO

        """
        
        response = gemini_model.generate_content(prompt)
        return response.text.strip().upper() == "YES"
        
    except Exception as e:
        print(f"Error checking relevance: {e}")
        return True  # Default to keeping posts if Gemini fails


# Load existing posts to avoid duplicates
filename = "classic_wow_posts.tsv"  # Changed to TSV for better Excel compatibility
existing_post_ids = set()

try:
    with open(filename, 'r', newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter='\t')  # Use tab delimiter for TSV
        for row in reader:
            # Extract post ID from permalink
            permalink = row['permalink']
            if '/comments/' in permalink:
                post_id = permalink.split('/comments/')[1].split('/')[0]
                existing_post_ids.add(post_id)
    print(f" Loaded {len(existing_post_ids)} existing posts from {filename}")
except FileNotFoundError:
    print(f" No existing file found, creating new {filename}")

# Collect posts from multiple Classic WoW subreddits
print("\n Collecting posts from multiple Classic WoW subreddits...")

subreddits_to_check = [
    "classicwowera",
    "classicwow",
    "wowclassic"
]

all_subreddit_posts = []
new_posts = []

# Collect posts from multiple subreddits and sorting methods
print(f"\nCollecting posts from multiple sources...")
try:
    # Collect from different subreddits
    all_posts = []
    
    for subreddit_name in subreddits_to_check:
        print(f"\n  Checking r/{subreddit_name}...")
        try:
            subreddit = reddit.subreddit(subreddit_name)
            
            # New posts (most recent)
            print(f"    Collecting from 'new' sorting...")
            new_posts = list(subreddit.new(limit=500))  # Reduced limit per subreddit
            all_posts.extend(new_posts)
            print(f"      Found {len(new_posts)} new posts")
            
            # Hot posts (popular recent)
            print(f"    Collecting from 'hot' sorting...")
            hot_posts = list(subreddit.hot(limit=500))
            all_posts.extend(hot_posts)
            print(f"      Found {len(hot_posts)} hot posts")
            
            # Top posts from different time periods
            print(f"    Collecting from 'top' sorting (all time)...")
            top_all_posts = list(subreddit.top(limit=500, time_filter='all'))
            all_posts.extend(top_all_posts)
            print(f"      Found {len(top_all_posts)} top all-time posts")
            
            print(f"    Collecting from 'top' sorting (year)...")
            top_year_posts = list(subreddit.top(limit=500, time_filter='year'))
            all_posts.extend(top_year_posts)
            print(f"      Found {len(top_year_posts)} top year posts")
            
        except Exception as e:
            print(f"    Error accessing r/{subreddit_name}: {e}")
            continue
    
    # Remove duplicates based on post ID
    unique_posts = {}
    for post in all_posts:
        if post.id not in unique_posts:
            unique_posts[post.id] = post
    
    subreddit_posts = list(unique_posts.values())
    print(f"\n  Total unique posts found across all subreddits: {len(subreddit_posts)}")
    
    processed_count = 0
    batch_size = 25  # Write to CSV every 25 posts
    current_batch = []
    
    for post in subreddit_posts:
        processed_count += 1
        if processed_count % 50 == 0:  # Show progress every 50 posts
            print(f"    Processed {processed_count} posts...")
            
        # Skip if post already exists
        if post.id in existing_post_ids:
            print(f"    Skipping existing: {post.title[:60]}...")
            continue
            
        post_content = f"Title: {post.title}\nContent: {post.selftext}"
        
        # Check if post is relevant using Gemini
        is_relevant = is_post_relevant(post_content)
        
        # Clean content to avoid TSV issues - remove newlines, tabs, and multiple spaces
        clean_title = ' '.join(post.title.replace('\t', ' ').replace('\n', ' ').replace('\r', ' ').split()).strip()
        clean_content = ' '.join(post.selftext.replace('\t', ' ').replace('\n', ' ').replace('\r', ' ').split()).strip()
        
        post_data = {
            'post_id': post.id,
            'subreddit': post.subreddit.display_name,
            'title': clean_title,
            'content': clean_content,
            'author': ' '.join(str(post.author).replace('\t', ' ').replace('\n', ' ').replace('\r', ' ').split()).strip(),
            'upvotes': post.score,
            'created_utc': post.created_utc,
            'permalink': f"https://reddit.com{post.permalink}",
            'answerable': 'YES' if is_relevant else 'NO'
        }
        current_batch.append(post_data)
        
        if is_relevant:
            print(f"   {post.title[:60]}... (upvotes: {post.score})")
        else:
            print(f"   {post.title[:60]}... (not relevant)")
         
        # Write batch to CSV every batch_size posts
        if len(current_batch) >= batch_size:
            # Get fieldnames from the first post
            fieldnames = current_batch[0].keys()
            
            # Append batch to existing file
            with open(filename, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\')  # Use tab delimiter, no quotes
                # Only write header if file is empty
                if f.tell() == 0:
                    writer.writeheader()
                writer.writerows(current_batch)
            
            print(f"     Saved batch of {len(current_batch)} posts to CSV...")
            new_posts.extend(current_batch)
            current_batch = []  # Reset batch
        
except Exception as e:
    print(f"Error collecting posts: {e}")

# Write any remaining posts in the final batch
if current_batch:
    fieldnames = current_batch[0].keys()
    with open(filename, 'a', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\')  # Use tab delimiter, no quotes
        if f.tell() == 0:
            writer.writeheader()
        writer.writerows(current_batch)
    new_posts.extend(current_batch)
    print(f"    💾 Saved final batch of {len(current_batch)} posts to TSV...")

print(f"\n Found {len(new_posts)} new posts from all Classic WoW subreddits")
print(f" All posts have been saved to {filename}")