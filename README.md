# Classic WoW RAG System

This project implements a Retrieval-Augmented Generation (RAG) system for Classic World of Warcraft questions. It scrapes game data, collects Reddit posts, and uses AI to provide accurate answers based on scraped information.

## Project Structure

```
Capstone/
├── scraper/
├── Reddit_API/
└── RAG_system/
```

The project consists of three main components:

1. **`scraper/`** - Web scraping for game data
2. **`Reddit_API/`** - Reddit post collection and analysis
3. **`RAG_system/`** - AI-powered question answering system

## Code Best Practices

Despite only importing one file, the project uses the `if __name__ == "__main__":` pattern throughout. This is a Python best practice that:

- **Prevents code execution** when modules are imported

Example:
```python
def main_function():
    # Main logic here
    pass

if __name__ == "__main__":
    main_function()
```

When you import this file, `main_function()` won't run. When you run the file directly, it will execute.

---

## Scraper Code Guidance

### Order of Operation
1. Scrape game data (items, quests)
2. Structure and clean the data
3. Generate CSV files for RAG system

### General Summary
The scraper extracts Classic WoW game data from various sources, focusing on items and quests. It handles dynamic content using Selenium and processes HTML with BeautifulSoup.

### Items

#### `scrape_items.py`
Focuses on scraping functions and HTML/JavaScript handling.

**Why Selenium instead of BeautifulSoup?**
- **Dynamic Content**: Many item pages load data via JavaScript after the initial HTML loads
- **Interactive Elements**: Some pages require clicking buttons or scrolling to reveal content
- **AJAX Requests**: Item data is often fetched asynchronously, which BeautifulSoup can't handle

**Main Functions:**
```python
def scrape_raid_items(raid_name, class_name, spec_name):
    """
    Scrapes items for a specific raid, class, and specialisation
    Handles JavaScript-loaded content and dynamic page elements
    """
    # Navigate to the page
    driver.get(url)
    
    # Wait for JavaScript content to load
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "item-list"))
    )
    
    # Extract item data
    items = driver.find_elements(By.CLASS_NAME, "item")
    # ... process items
```

**JavaScript Click with Selenium:**
```python
# Click element using JavaScript when normal click fails
element = driver.find_element(By.ID, "load-more")
driver.execute_script("arguments[0].click();", element)
```

Reference: [How to click an element in Selenium WebDriver using JavaScript](https://stackoverflow.com/questions/11947832/how-to-click-an-element-in-selenium-webdriver-using-javascript)

#### `structure_items.py`
Focuses on BeautifulSoup parsing and weapon type classification.

**The Problem of Weapon Classification:**
Classic WoW has complex weapon rules that require looking up actual item data:
- **Main Hand Only**: Weapons that can only be equipped in the main hand slot
- **Two-Hand**: Two-handed weapons that occupy both main hand and off hand slots
- **One-Hand**: One-handed weapons that can be equipped in either main hand or off hand
- **Off Hand**: Items specifically designed for the off hand slot (shields, held in off-hand)
- **Ranged**: Bows, guns, wands, and relics that go in the ranged slot

**Main Functions:**
```python
def categorise_weapon(item_id):
    """
    Look up weapon on classicdb.ch and categorise it based on HTML structure
    Uses the actual equipment slot information from the item page
    """
    response = requests.get(f"https://classicdb.ch/?item={item_id}", timeout=10)
    soup = BeautifulSoup(response.content, 'html.parser')

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
```

**New Methods Explained:**
- **`unescape()`**: Converts HTML entities (like `&amp;`) back to normal characters
- **`decompose()`**: Removes an element and all its children from the DOM tree
- **`DOTALL`**: Regex flag that makes `.` match newlines (useful for multi-line text)
- **`glob`**: Pattern matching for file paths (e.g., `*.txt` matches all text files)

#### `create_weapon_lookup.py`
Creates a lookup table mapping weapon names to their correct classifications.

**What it does:**
- Reads scraped weapon data
- Applies classification rules
- Generates a lookup file for the RAG system
- Ensures consistent weapon categorisation across the system


### Quests

#### `scrape_quests.py`
General purpose quest data extraction from Classic WoW database.

**Main Functions:**
```python
def scrape_quest_data(quest_name):
    """
    Extracts quest information including objectives, rewards, and requirements
    Handles dynamic content loading and interactive elements
    """
    # Navigate to quest page
    driver.get(quest_url)
    
    # Use ActionChains for complex interactions
    actions = ActionChains(driver)
    actions.move_to_element(reward_element).perform()
    
    # Extract quest data
    quest_info = parse_quest_page(driver.page_source)
    return quest_info
```

**Selenium ActionChains:**
ActionChains are "useful for complex interactions like hovering, drag and drop, and multi-step actions."

```python
from selenium.webdriver.common.action_chains import ActionChains

# Hover over element then click
actions = ActionChains(driver)
actions.move_to_element(element).click().perform()

# Drag and drop
actions.drag_and_drop(source, target).perform()
```

Reference: [Action Chains in Selenium Python](https://www.geeksforgeeks.org/python/action-chains-in-selenium-python/)

**The Problem of Reward Identification:**
Classic WoW quests have different reward types:
- **Pick Selection**: Player chooses from multiple reward options
- **Guaranteed**: Player receives all listed rewards

This affects how the RAG system presents reward information to users.

#### `generate_csv.py`
Converts scraped data into CSV format for the RAG system.

**Main Functions:**
```python
def write_to_csv(data, filename):
    """
    Writes structured data to CSV file
    Handles special characters and proper formatting
    """
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Name', 'Type', 'Data'])  # Headers
        
        for item in data:
            writer.writerow([item['name'], item['type'], item['data']])
```

**CSV Writing Best Practices:**
- Use `newline=''` to handle line ending differences across operating systems
- Specify `encoding='utf-8'` for proper character handling
- Use `csv.writer()` for automatic escaping of special characters

Reference: [How to write to a CSV file](https://docs.python.org/3/library/csv.html)

---

## Reddit_API code guidance

### Order of Operation
1. Collect Reddit posts from relevant subreddits
2. Analyse posts for answerability
3. Process answerable posts with RAG system

### General Summary
The Reddit API component collects and analyses Classic WoW Reddit posts, determining which can be answered with scraped game data.

#### `collect_posts.py`
Collects Reddit posts using PRAW (Python Reddit API Wrapper).

**Main Functions:**
```python
def collect_reddit_posts():
    """
    Collects posts from Classic WoW subreddits
    Filters for relevance and saves to TSV file
    """
    reddit = praw.Reddit(
        client_id=credentials["client_id"],
        client_secret=credentials["client_secret"],
        username=credentials["username"],
        password=credentials["password"],
        user_agent="ClassicRAGBot/1.0"
    )
    
    # Collect posts from multiple subreddits
    subreddits = ['classicwow', 'wowclassic']
    for subreddit in subreddits:
        posts = reddit.subreddit(subreddit).hot(limit=100)
        process_posts(posts)
```

**PRAW Configuration:**
- **Client ID/Secret**: From Reddit app settings
- **Username/Password**: Reddit account credentials
- **User Agent**: Identifies your bot to Reddit

Reference: [PRAW Quick Start Guide](https://praw.readthedocs.io/en/stable/getting_started/quick_start.html)

#### `analyse_posts.py`
Determines the number of Reddit posts answerable with complete data vs. current scraped data.

**What it does:**
- Analyses each Reddit post for answerability
- Classifies posts as "answerable" with complete wiki data or "subjective"
- Provides insights into data coverage and gaps

**Key Numbers from TSV Analysis:**
- **86.4% (2,552)** of posts are subjective and not answerable even with complete wiki data
- **13.6% (402)** are answerable with complete wiki data
- **3.4% (100)** are answerable with current scraped data

**Main Functions:**
```python
def analyse_post_type(post_title, post_content):
    """
    Determines if a post can be answered with game data
    Uses Gemini AI to classify post types
    """
    prompt = f"""
    Analyse this Reddit post and determine if it can be answered with Classic WoW game data:
    
    Title: {post_title}
    Content: {post_content}
    
    Classify as:
    - "answerable" with wiki data if it asks for factual game information
    - "subjective" if it's opinion-based or requires personal experience
    """
    
    response = gemini_model.generate_content(prompt)
    return classify_response(response.text)
```

---

## RAG_system code guidance

### Order of Operation
1. Initialise Google Cloud services and AI models
2. Create BigQuery table for vector storage
3. Process input data and generate embeddings
4. Query system using cosine similarity search
5. Generate AI-powered responses

### General Summary
The RAG system combines vector search with AI generation to provide accurate answers to Classic WoW questions based on scraped game data.

#### `simple_rag.py`
Core RAG system implementation with Google Cloud integration.

**Main Functions:**
```python
class SimpleRAG:
    def __init__(self, project_id, gemini_api_key):
        """
        Initialise the RAG system with Google Cloud services
        Sets up BigQuery, Vertex AI, and Gemini
        """
        # Set Google Application Credentials
        service_account_path = Path(__file__).parent / 'service-account-key.json'
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(service_account_path)
        
        # Initialise BigQuery client
        self.bq_client = bigquery.Client(project=project_id)
        
        # Initialise Vertex AI for embeddings
        vertexai.init(project=project_id, location="us-central1")
        self.embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-005")
        
        # Initialise Gemini for text generation
        genai.configure(api_key=gemini_api_key)
        self.gemini_model = genai.GenerativeModel("gemini-1.5-flash")
```

**Google Application Credentials:**
The system sets the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to authenticate with Google Cloud services.

Reference: [Set Google Application Credentials in Python Project](https://stackoverflow.com/questions/45501082/set-google-application-credentials-in-python-project-to-use-google-api)

**BigQuery Client:**
Used for storing and querying vector embeddings and game data.

Reference: [BigQuery Python Client Library](https://cloud.google.com/python/docs/reference/bigquery/latest)

**Vertex AI Initialisation:**
Sets up the text embedding model for converting text to vectors.

Reference: [Vertex AI Text Embeddings API](https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/text-embeddings-api#python)

**BigQuery Table Creation:**
Creates tables with proper schemas for storing vector data.

```python
def _create_table(self):
    """
    Creates BigQuery table for storing embeddings and game data
    Includes vector columns for similarity search
    """
    schema = [
        bigquery.SchemaField("id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("content", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("embedding", "FLOAT64", mode="REPEATED"),
        bigquery.SchemaField("metadata", "STRING", mode="NULLABLE")
    ]
    
    table = bigquery.Table(f"{self.project_id}.dataset.table_name", schema=schema)
    self.bq_client.create_table(table, exists_ok=True)
```

Reference: [BigQuery Table Creation](https://cloud.google.com/bigquery/docs/tables#create_an_empty_table_with_a_schema_definition)

**Cosine Similarity Search:**
Uses BigQuery SQL to find similar content using vector embeddings.

```python
def query(self, question, top_k=5, similarity_threshold=0.5):
    """
    Query the RAG system using cosine similarity search
    Returns AI-generated answers based on retrieved content
    """
    # Generate question embedding
    question_embedding = self.embedding_model.get_embeddings([question])[0]
    
    # BigQuery SQL for cosine similarity
    query = f"""
    SELECT content, metadata,
           (ARRAY_TO_STRING(embedding, ',') * ARRAY_TO_STRING({question_embedding}, ',')) / 
           (SQRT(ARRAY_TO_STRING(embedding, ',') * ARRAY_TO_STRING(embedding, ',')) * 
            SQRT(ARRAY_TO_STRING({question_embedding}, ',') * ARRAY_TO_STRING({question_embedding}, ','))) as similarity_score
    FROM `{self.project_id}.dataset.table_name`
    WHERE similarity_score >= {similarity_threshold}
    ORDER BY similarity_score DESC
    LIMIT {top_k}
    """
    
    results = self.bq_client.query(query).result()
    return self.generate_answer(question, results)
```

Reference: [Cosine Similarity in BigQuery](https://stackoverflow.com/questions/53927630/cosine-similarity-between-pair-of-arrays-in-bigquery) (Note: Formula is slightly different in my implementation)

---

## Steps to Reproduce

### Prerequisites
1. **Google Cloud Service Account** with "Vertex AI User" and "BigQuery Admin" permissions
2. **Gemini API Key** for AI text generation
3. **Reddit API App** credentials (set subreddit preferences in `collect_posts.py`)
4. **Your own dataset** in CSV format for processing

### Setup Steps
1. **Place credential files:**
   - `RAG_system/service-account-key.json` - Google Cloud service account key
   - `RAG_system/credentials.json` - Project ID and Gemini API key
   - `Reddit_API/reddit_credentials.json` - Reddit API credentials

2. **Install dependencies:**
   ```bash
   pip install google-cloud-bigquery google-cloud-aiplatform google-generativeai praw beautifulsoup4 selenium pandas
   ```

3. **Configure variables:**
   - **BigQuery dataset and table names** in `simple_rag.py` (lines 47-48)
   - **File paths** in `simple_rag.py` for your CSV data

4. **Run the system:**
   ```bash
   # Collect Reddit posts
   python Reddit_API/collect_posts.py
   
   # Analyse posts
   python Reddit_API/analyse_posts.py
   
   # Run RAG system
   python RAG_system/simple_rag.py
   ```

---

The project demonstrates how to build a focused RAG system that provides accurate answers to specific types of questions (quests and items) rather than attempting to cover all possible game-related queries.
