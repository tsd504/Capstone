# Classic WoW Data Collection & RAG System

This project collects Classic World of Warcraft data from various sources, processes it, and creates a Retrieval-Augmented Generation (RAG) system for answering questions about the game.

## Project Structure

```
Github/
├── scraper/           # Data collection from WoWHead
├── Reddit_API/        # Reddit post collection and analysis
└── RAG_system/        # Vector search and question answering
```

---

## Scraper Code Guidance

### Items

**Order of operation:** `scrape_items.py` → `structure_items.py` → `create_weapon_lookup.py` → `structure_items.py` (run again)

#### 1. scrape_items.py
Scrapes item data from WarcraftLogs for each class, spec, and raid combination. Uses BeautifulSoup to parse HTML and extract item information.

**Key concepts:**
- **Web scraping with BeautifulSoup:** Parses HTML to extract structured data from websites
- **Rate limiting:** Includes delays between requests to avoid overwhelming the server
- **File organisation:** Creates nested directory structure based on raid/class/spec

**Main methods:**
```python
def find_raid_urls(driver):
    """Finds all raid URLs from the main page"""
    # Scrapes raid links and saves them for processing

def save_players(driver, raid_urls, class_spec_extensions):
    """Main function that scrapes player data for all raids"""
    # Iterates through raids and extracts player information
    # Creates directory structure: scraped_items/Raid/Class/Spec.txt
```

#### 2. structure_items.py
Takes the raw scraped data and converts it into a structured format suitable for analysis. Cleans up the text, standardises formatting, and creates consistent data structures.

**Key concepts:**
- **Data normalisation:** Standardises text formatting and removes inconsistencies
- **Text cleaning:** Removes HTML tags and extra whitespace

**Main methods:**
```python
def extract_player_data(html_content):
    """Extracts structured player data from HTML content"""
    # Parses HTML tables to extract player information
    # Returns clean, structured data

def process_all_files():
    """Main function that processes all scraped files"""
    # Iterates through all scraped files and structures them
```

#### 3. create_weapon_lookup.py
Creates a lookup table for weapons to help with data organisation and cross-referencing.

**Main methods:**
```python
def create_weapon_lookup():
    """Creates a comprehensive weapon lookup table"""
    # Categorises weapons by type and creates lookup mappings
```

#### 4. structure_items.py (second run)
Runs the structuring process again on the updated data to ensure consistency.

### Quests

**Order of operation:** Just run `scrape_quests.py` (calls `scrape_comments.py` automatically)

#### 1. scrape_quests.py
Scrapes quest information from classicdb.ch, including quest details, requirements, rewards, and comments. Automatically calls the comments scraper for each quest.

**Key concepts:**
- **Recursive scraping:** Automatically triggers comment scraping for each quest found
- **Data extraction patterns:** Uses consistent patterns to extract quest information

**Main methods:**
```python
def scrape_quest_data(driver):
    """Main function that scrapes all quests and automatically calls comment scraping"""
    # Iterates through quest categories
    # Calls scrape_comments.py for each quest found

def extract_quest_data_from_row(row, driver):
    """Extracts quest information from a table row"""
    # Parses quest details including requirements and rewards
```

#### 2. scrape_comments.py
Scrapes user comments for each quest, providing additional context and community knowledge.

**Main methods:**
```python
def scrape_quest_details(quest_extension):
    """Scrapes detailed quest information and comments"""
    # Extracts quest description, progress, and user comments
```

### generate_csv.py
Combines all the scraped data into CSV files for easy analysis and import into other systems.

**Main methods:**
```python
def generate_item_csv():
    """Combines all item data into a single CSV file"""

def generate_quest_csv():
    """Combines all quest data into a single CSV file"""
```

---

## Reddit_API Code Guidance

**Order of operation:** `collect_posts.py` → `analyse_posts.py`

### 1. collect_posts.py
Collects Reddit posts from Classic WoW subreddits using the PRAW (Python Reddit API Wrapper) library. Filters posts for relevance using Gemini AI and saves them to a TSV file.

**Key concepts:**
- **PRAW authentication:** Uses Reddit's API with OAuth2 authentication
- **Batch processing:** Processes posts in batches to avoid memory issues
- **Duplicate detection:** Checks for existing posts to avoid re-processing
- **AI-powered filtering:** Uses Gemini to determine if posts are answerable with game data
- **TSV formatting:** Uses tab-separated values for better Excel compatibility
- **Character encoding:** Uses `utf-8-sig` encoding to handle special characters properly

**Main methods:**
```python
def is_post_relevant(post_content):
    """Uses Gemini AI to determine if a post can be answered with game data"""
    prompt = f"""
    You have data on Classic WoW raids and quests.
    Can this Reddit post be answered using this data?
    Post: {post_content}
    Respond with only: YES or NO
    """
    response = gemini_model.generate_content(prompt)
    return response.text.strip().upper() == "YES"
```

**Technical details:**
- **Character encoding issues:** The black diamond characters () you might see in Excel are caused by inconsistent encoding between reading and writing files. Using `utf-8-sig` for both operations fixes this.
- **Text cleaning:** Removes newlines, tabs, and multiple spaces to prevent TSV formatting issues

### 2. analyse_posts.py
Analyses the collected Reddit posts to determine which ones could be answered with wiki data versus subjective questions.

**Key concepts:**
- **Post classification:** Uses AI to categorise posts as factual vs subjective
- **Data enrichment:** Adds new columns to existing data

**Main methods:**
```python
def analyse_post_type(post_content):
    """Analyses if a post is answerable with wiki data or is subjective"""
    prompt = f"""
    You are analysing Reddit posts to determine if they can be answered with factual game data.
    A post is "YES" if it asks for item locations, quest info, class abilities, etc.
    A post is "NO" if it asks for personal preferences or opinions.
    Post: {post_content}
    Respond with only: YES or NO
    """
```

---

## RAG_system Code Guidance

**Order of operation:** `simple_rag.py`

### 1. simple_rag.py
Creates a Retrieval-Augmented Generation system that can answer questions about Classic WoW using the collected data.

**Key concepts:**
- **Vector embeddings:** Converts text into numerical representations (vectors) that capture semantic meaning
- **BigQuery integration:** Uses Google BigQuery for storing and querying vector data
- **Cosine similarity:** Mathematical method for comparing how similar two vectors are
- **RAG architecture:** Combines retrieval (finding relevant documents) with generation (creating answers)

**Main methods:**
```python
def query(self, question, top_k=3):
    """Main query method that implements the RAG process"""
    # 1. Convert question to embedding vector
    question_embedding = self.embedding_model.get_embeddings([question])[0].values
    
    # 2. Search BigQuery for similar documents using cosine similarity
    # 3. Retrieve top-k most similar documents
    # 4. Generate answer using Gemini
```

**Technical concepts explained:**

**Vector Embeddings:**
- Text is converted into fixed-size vectors
- Each number represents some semantic feature
- Similar meanings produce similar vectors (e.g., "sword" and "weapon" have similar embeddings)
- The model learned to encode meaning into numbers during training

**Cosine Similarity:**
- Measures the angle between two vectors in high-dimensional space
- Range: -1 to 1, where 1 = identical, 0 = unrelated, -1 = opposite
- Formula: `cos(θ) = (A·B) / (|A| × |B|)`
- Used to find the most relevant documents for a query

**BigQuery Vector Operations:**
- **UNNEST:** Flattens arrays into individual rows for mathematical operations
- **WITH OFFSET:** Tracks the position of each element when unnesting arrays
- **USING (pos):** Joins arrays based on position to ensure corresponding elements are compared
- **Array literals:** BigQuery expects arrays in string format like `[0.1,-0.3,0.7,-0.2]`

**Why UNNEST is needed:**
- BigQuery stores embeddings as arrays: `[-0.01545286, 0.015474392, ...]`
- You can't do math on arrays directly: `array * array` doesn't work
- UNNEST flattens arrays so you can calculate dot products: `element1 * element2`

**RAG Process:**
1. Convert user question to embedding vector
2. Find most similar document embeddings using cosine similarity
3. Retrieve the actual text of those documents
4. Use Gemini to generate an answer based on the retrieved context

#### Example flow:
```
Question: "What's the best weapon for a warrior?"
↓
Embedding: [0.1, -0.3, 0.7, -0.2, ...]
↓
SQL query finds similar document embeddings
↓
Retrieves: "Rank: 1 || Name: ... || Weapon: ..."
↓
Gemini generates: "Based on the data, ... appears to be..."
```

**Similar BigQuery Implementation:**
The cosine similarity calculation in this code is very similar to the approach shown in [this Stack Overflow answer](https://stackoverflow.com/questions/53927630/cosine-similarity-between-pair-of-arrays-in-bigquery), which demonstrates the same UNNEST pattern for calculating cosine similarity between arrays in BigQuery.

---

## Useful Resources

### Web Scraping
- [BeautifulSoup Documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [W3Schools - Python Web Scraping](https://www.w3schools.com/python/python_web_scraping.asp)

### Reddit API
- [PRAW Documentation](https://praw.readthedocs.io/)
- [Reddit API Guide](https://github.com/reddit-archive/reddit/wiki/API)

### Vector Similarity
- [Cosine Similarity - Stack Overflow](https://stackoverflow.com/questions/1746501/can-someone-give-an-example-of-cosine-similarity-in-a-very-simple-graphical-wa)
- [Vector Similarity Search - Pinecone](https://www.pinecone.io/learn/vector-similarity/)

### BigQuery
- [BigQuery Documentation](https://cloud.google.com/bigquery/docs)
- [BigQuery Arrays - Google Cloud](https://cloud.google.com/bigquery/docs/reference/standard-sql/arrays)
- [BigQuery Cosine Similarity Example](https://stackoverflow.com/questions/53927630/cosine-similarity-between-pair-of-arrays-in-bigquery) - Shows very similar code to what's implemented here

### RAG Systems
- [RAG Architecture - Pinecone](https://www.pinecone.io/learn/retrieval-augmented-generation/)

---
