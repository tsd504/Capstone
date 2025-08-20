import csv
import google.generativeai as genai
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

def analyse_post_type(post_content):
    """Analyse if a post is answerable with wiki data or is subjective"""
    try:
        prompt = f"""
        You are analysing Reddit posts about Classic World of Warcraft to determine if they can be answered with factual game data or if they are subjective questions.

        A post is "YES" (answerable with wiki data) if it asks for:
        - Item locations, drop rates, requirements
        - Quest information, NPC locations
        - Class abilities, spell details
        - Boss mechanics, loot tables
        - Profession information, crafting recipes

        A post is "NO" (subjective/couldn't answer even with wiki data) if it asks for:
        - Personal preferences or opinions
        - What class/spec is "best" or "most fun"
        - Whether something is "worth it" or "good"
        - Community opinions or experiences
        - Aesthetic choices or roleplay decisions
        - Guild recommendations or social advice
        - General discussion topics without specific questions

        Post to analyse:
        {post_content}

        Respond with only: YES or NO
        """
        
        response = gemini_model.generate_content(prompt)
        return response.text.strip().upper()
        
    except Exception as e:
        print(f"Error analysing post type: {e}")
        return "ERROR"  # Default if Gemini fails

def main():
    # Load the collected posts
    filename = "classic_wow_posts.tsv"
    
    # Statistics
    total_posts = 0
    answerable_with_data = 0
    answerable_with_wiki = 0
    subjective_questions = 0
    errors = 0
    
    # Read existing data and add new column
    updated_rows = []
    
    try:
        with open(filename, 'r', newline='', encoding='utf-8-sig', errors='replace') as f:
            reader = csv.DictReader(f, delimiter='\t')
            
            for row in reader:
                total_posts += 1
                
                # Show progress every 100 posts
                if total_posts % 100 == 0:
                    print(f"Processed {total_posts} posts...")
                
                # Get post content
                title = row['title']
                content = row['content']
                post_content = f"Title: {title}\nContent: {content}"
                
                # Analyse post type
                post_type = analyse_post_type(post_content)
                
                # Update statistics
                if post_type == "YES":
                    answerable_with_wiki += 1
                elif post_type == "NO":
                    subjective_questions += 1
                else:
                    errors += 1
                
                # Check if it was marked as answerable by your original script
                was_marked_answerable = row['answerable'] == 'YES'
                if was_marked_answerable:
                    answerable_with_data += 1
                
                # Add the new column to the row
                row['wiki_answerable'] = post_type
                updated_rows.append(row)
                
                # Add a small delay to avoid rate limiting
                import time
                time.sleep(0.1)
                
    except FileNotFoundError:
        print(f"Error: Could not find {filename}")
        return
    
    # Write updated data back to the same file
    print(f"\nUpdating {filename} with new column...")
    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        # Get all fieldnames including the new one
        fieldnames = list(updated_rows[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t')
        writer.writeheader()
        writer.writerows(updated_rows)
    
    # Print summary
    print(f"Total posts analysed: {total_posts}")
    print(f"Posts marked as answerable by your data: {answerable_with_data}")
    print(f"Posts answerable with wiki data: {answerable_with_wiki}")
    print(f"Subjective/couldn't answer: {subjective_questions}")
    print(f"Analysis errors: {errors}")
    
    # Calculate percentages
    if total_posts > 0:
        data_answerable_pct = (answerable_with_data / total_posts) * 100
        wiki_answerable_pct = (answerable_with_wiki / total_posts) * 100
        subjective_pct = (subjective_questions / total_posts) * 100
        
        print(f"\n📈 PERCENTAGES:")
        print(f"Answerable with your data: {data_answerable_pct:.1f}%")
        print(f"Answerable with wiki data: {wiki_answerable_pct:.1f}%")
        print(f"Subjective/couldn't answer: {subjective_pct:.1f}%")
        
        # Calculate overlap
        overlap = min(answerable_with_data, answerable_with_wiki)
        overlap_pct = (overlap / total_posts) * 100
        print(f"Overlap (your data + wiki data): {overlap_pct:.1f}%")
        
        print(f"\n🎯 CONCLUSION:")
        print(f"Your data covers {data_answerable_pct:.1f}% of posts, but {wiki_answerable_pct:.1f}%")
        print(f"could be answered with wiki data, and {subjective_pct:.1f}% are subjective questions.")
        print(f"This means your data is actually quite valuable for the factual questions!")
        print(f"\nThe TSV file has been updated with a new 'wiki_answerable' column!")

if __name__ == "__main__":
    main()
