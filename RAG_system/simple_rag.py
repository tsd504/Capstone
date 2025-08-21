from datetime import datetime
from pathlib import Path
import pandas as pd
import json
import os

# Google Cloud imports
from google.cloud import bigquery
import vertexai
from vertexai.preview.language_models import TextEmbeddingModel
import google.generativeai as genai

class SimpleRAG:
    def __init__(self, project_id, gemini_api_key):

        self.project_id = project_id
        
        # Service account credentials needed to access bigquery and vertex ai
        service_account_path = Path(__file__).parent / 'service-account-key.json'
        if service_account_path.exists():
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(service_account_path)
            print("Using service-account-key.json file for Google Cloud authentication")
        else:
            raise FileNotFoundError("service-account-key.json not found")
        
        # Initialise BigQuery
        self.bq_client = bigquery.Client(project=project_id)
        
        # Initialise Vertex AI
        vertexai.init(project=project_id, location="us-central1")
        
        # Initialise embedding model
        self.embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-005")
        print("Vertex AI embedding model ready")
        
        # Initialise Gemini
        genai.configure(api_key=gemini_api_key)
        self.gemini_model = genai.GenerativeModel("gemini-1.5-flash")
        print("Gemini model ready")
        
        # Create BigQuery table
        self._create_table()
    
    def _create_table(self):
        """Create the BigQuery table for storing embeddings"""
        dataset_id = f"{self.project_id}.rag_dataset"
        table_id = f"{dataset_id}.embeddings"
        
        # Create dataset
        dataset = bigquery.Dataset(dataset_id)
        dataset.location = "us-central1"
        self.bq_client.create_dataset(dataset, exists_ok=True)
        print("BigQuery dataset ready")
        
        # Create table
        schema = [
            bigquery.SchemaField("id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("text", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("embedding", "FLOAT64", mode="REPEATED"),
            bigquery.SchemaField("source", "STRING", mode="REQUIRED")
        ]
        
        table = bigquery.Table(table_id, schema=schema)
        self.bq_client.create_table(table, exists_ok=True)
        print("BigQuery table ready")
        
        self.table_id = table_id
    
    def _get_existing_row_ids(self, source_filename):
        """Get existing row IDs for this source to avoid duplicates"""
        try:
            query = f"""
            SELECT id
            FROM `{self.table_id}`
            WHERE source = '{source_filename}'
            """
            query_job = self.bq_client.query(query)
            results = query_job.result()
            return {row.id for row in results}
        except Exception as e:
            print(f"Warning: Could not check existing data: {e}")
            return set()
    
    def process_csv(self, csv_file_path):
        """Process a CSV file and store embeddings in BigQuery"""
        print(f"Processing: {csv_file_path}")
        
        # Get existing row IDs to avoid duplicates
        source_filename = Path(csv_file_path).name
        existing_ids = self._get_existing_row_ids(source_filename)
        if existing_ids:
            print(f"Found {len(existing_ids)} existing rows for {source_filename}. Will skip duplicates.")
        
        # Read CSV
        df = pd.read_csv(csv_file_path)
        print(f"Loaded {len(df)} rows")
        
        # Convert each row to text
        texts = []
        for index, row in df.iterrows():
            # Convert row to text format
            row_text = " || ".join([f"{col}: {val}" for col, val in row.items() if pd.notna(val)])
            
            # No truncation - preserve all data
            
            texts.append(row_text)
        
        # Check for any extremely long texts
        max_length = max(len(text) for text in texts)
        print(f"Longest text chunk: {max_length} characters")
        
        print(f"Created {len(texts)} text chunks")
        
        # Get embeddings (in small batches to avoid errors)
        print("Getting embeddings...")
        all_embeddings = []
        batch_size = 10  # Process one row at a time to avoid token limits
        
        total_batches = (len(texts) + batch_size - 1) // batch_size
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            current_batch = i // batch_size + 1
            print(f"Processing batch {current_batch}/{total_batches}")
            
            # Get embeddings for this batch
            responses = self.embedding_model.get_embeddings(batch)
            batch_embeddings = [r.values for r in responses]
            all_embeddings.extend(batch_embeddings)
        
        print("Got all embeddings")
        
        # Store in BigQuery
        print("Storing in BigQuery...")
        rows_to_insert = []
        for i, (text, embedding) in enumerate(zip(texts, all_embeddings)):
            row_id = f"{source_filename}_{i}"
            
            # Skip if this row already exists
            if row_id in existing_ids:
                print(f"Skipping row {i} (already exists)")
                continue
                
            rows_to_insert.append({
                "id": row_id,
                "text": text,
                "embedding": embedding,
                "source": source_filename
            })
        
        # Insert in batches
        insert_batch_size = 100
        total_insert_batches = (len(rows_to_insert) + insert_batch_size - 1) // insert_batch_size
        for i in range(0, len(rows_to_insert), insert_batch_size):
            batch = rows_to_insert[i:i + insert_batch_size]
            current_batch = i // insert_batch_size + 1
            self.bq_client.insert_rows_json(self.table_id, batch)
            print(f"Inserted batch {current_batch}/{total_insert_batches}")
        
        print("All data stored in BigQuery!")
    
    def query(self, question, top_k=3, similarity_threshold=0.5):
        """
        Query the RAG system
        
        question: The question to answer
        top_k: Number of similar documents to retrieve (default 3)
        similarity_threshold: Minimum similarity score (default 0.5)
        """
        
        # Get embedding for the question
        question_embedding = self.embedding_model.get_embeddings([question])[0].values
        
        # Convert to string for BigQuery
        embedding_str = "[" + ",".join(map(str, question_embedding)) + "]"
        
        # Search in BigQuery
        query_sql = f"""
        WITH query_embedding AS (
            SELECT {embedding_str} as embedding
        ),
        similarities AS (
            SELECT 
                text,
                source,
                -- Simple cosine similarity
                (SELECT SUM(a * b) / (SQRT(SUM(a * a)) * SQRT(SUM(b * b)))
                FROM UNNEST(embedding) AS a WITH OFFSET pos
                JOIN UNNEST((SELECT embedding FROM query_embedding)) AS b WITH OFFSET pos
                USING (pos)
                ) as similarity_score
            FROM `{self.table_id}`
        )
        SELECT text, source, similarity_score
        FROM similarities
        WHERE similarity_score IS NOT NULL
        AND similarity_score >= {similarity_threshold}
        ORDER BY similarity_score DESC
        LIMIT {top_k}
        """
        
        # Run the query
        query_job = self.bq_client.query(query_sql)
        results = query_job.result()
        
        # Get the most similar texts
        similar_texts = []
        for row in results:
            similar_texts.append({
                "text": row.text,
                "source": row.source,
                "score": row.similarity_score
            })
        
        if not similar_texts:
            return "No relevant information found."
        
        # Create context from similar texts
        context = "\n\n".join([item["text"] for item in similar_texts])
        
        # Determine optimal K based on question type
        if any(word in question.lower() for word in ['item', 'weapon', 'armor', 'gear', 'equipment']):
            # For item questions, get more data for better aggregation
            dynamic_k = 70
        else:
            # For quest questions, fewer results are fine
            dynamic_k = top_k
            
        # Re-run query with dynamic K if needed
        if dynamic_k != top_k:
            query_sql_dynamic = query_sql.replace(f"LIMIT {top_k}", f"LIMIT {dynamic_k}")
            query_job = self.bq_client.query(query_sql_dynamic)
            results = query_job.result()
            
            # Re-process results
            similar_texts = []
            for row in results:
                similar_texts.append({
                    "text": row.text,
                    "source": row.source,
                    "score": row.similarity_score
                })
        
        # Generate response with Gemini
        prompt = f"""
        System Instructions:
        Based on this information, answer the question. If the information doesn't contain the answer, say so.
        
        Raid Abbreviations:
        - Molten Core = MC
        - Onyxia = Ony
        - Blackwing Lair = BWL
        - Zul'Gurub = ZG
        - Ruins of Ahn'Qiraj = AQ20
        - Temple of Ahn'Qiraj = AQ40
        
        For ITEM questions:
        - When someone asks for "best" items, interpret this as "most commonly worn" items
        - Our data shows what top players actually wear, so "best" = "most popular among top players"
        - Provide aggregate data showing which items appear most frequently
        - Use raid abbreviations when referring to raids (MC, BWL, AQ40, etc.)
        
        For QUEST questions:
        - Focus on exact quest name matches when possible
        - If multiple quests seem relevant, prioritise the one with the most direct name match
        - Provide complete quest information (location, requirements, rewards, etc.)
        - Don't mix up different quests - stick to the most relevant single quest

        Information:
        {context}

        Question: {question}

        Answer:
        """
        
        response = self.gemini_model.generate_content(prompt)
        return response.text
    
    def process_reddit_posts(self):
        """
        Process Reddit posts from TSV file and add RAG responses
        Only processes posts that have answerable = 'yes'
        """
        # Path to the Reddit posts TSV file
        tsv_path = Path(__file__).parent.parent / "Reddit_API" / "classic_wow_posts.tsv"
        
        if not tsv_path.exists():
            print(f"Reddit posts file not found: {tsv_path}")
            return
        
        print(f"Processing Reddit posts from: {tsv_path}")
        
        # Read the TSV file
        df = pd.read_csv(tsv_path, sep='\t', encoding='utf-8-sig')
        print(f"Loaded {len(df)} Reddit posts")
        
        # Check if 'rag_response' column exists, if not create it
        if 'rag_response' not in df.columns:
            df['rag_response'] = ''
            print("Added 'rag_response' column")
        
        # Process only posts that have answerable = 'YES' and don't have RAG responses yet
        answerable_posts = df[(df['answerable'] == 'YES') & 
                             (df['rag_response'].isna() | (df['rag_response'] == ''))]
        
        print(f"Found {len(answerable_posts)} answerable posts without RAG responses")
        
        if len(answerable_posts) == 0:
            print("All answerable posts already have RAG responses!")
            return
        
        # Process each answerable post
        for i, (index, row) in enumerate(answerable_posts.iterrows()):
            post_title = row.get('title', '')
            post_content = row.get('content', '')
            
            # Combine title and content for the query
            full_post = f"Title: {post_title}\n\nContent: {post_content}"
            
            print(f"\nProcessing post {i + 1}/{len(answerable_posts)}: {post_title[:50]}...")
            
            try:
                # Get RAG response
                rag_response = self.query(full_post)
                
                # Update the dataframe
                df.at[index, 'rag_response'] = rag_response
                
                print(f" Generated response ({len(rag_response)} characters)")
                
                # Save after each post to avoid losing progress
                df.to_csv(tsv_path, sep='\t', index=False, encoding='utf-8-sig')
                print(f" Saved to file")
                
            except Exception as e:
                print(f" Error processing post {index}: {e}")
                # Continue with next post
                continue
        
        print(f"\nCompleted processing {len(answerable_posts)} answerable Reddit posts!")
        print(f"Updated file: {tsv_path}")
    
def main():

    print("Simple RAG System")
    print()
    
    # Load credentials from JSON file
    credentials_path = Path(__file__).parent / 'credentials.json'
    try:
        with open(credentials_path, 'r') as f:
            credentials = json.load(f)
        PROJECT_ID = credentials["project_id"]
        GEMINI_API_KEY = credentials["gemini_api_key"]
        print("Loaded credentials from credentials.json")
    except FileNotFoundError:
        print("Warning: credentials.json not found. Make sure it's in the same directory as this script.")
        exit(1)
    
    try:
        # Create RAG system
        print("Setting up RAG system...")
        rag = SimpleRAG(credentials["project_id"], credentials["gemini_api_key"])
        print("RAG system ready!")
        print()
        
        # NOTE: Only process CSV files if you want to update the database. Otherwise keep commented out.
        # script_dir = Path(__file__).parent
        # CSV_FILES = [
        #     script_dir.parent / "scraper" / "items_combined.csv",
        #     script_dir.parent / "scraper" / "quests_combined.csv"
        # ]
        # # Process CSV files
        # print("Processing CSV files...")
        # for csv_file in CSV_FILES:
        #     if csv_file.exists():
        #         rag.process_csv(str(csv_file))
        #         print()
        #     else:
        #         print(f"File not found: {csv_file}")
        # print()
        
        # NOTE:Test manual queries
        # prompt = input("Prompt: ")
        # while prompt.lower() != "exit":
        #     print(f"\nQ: {prompt}")
        #     answer = rag.query(prompt)
        #     print(f"A: {answer}")
        #     print("-" * 50)
        #     prompt = input("Prompt: ")

        # NOTE: Test reddit posts
        # print("Processing Reddit posts...")
        # rag.process_reddit_posts()
        
        print("\nAll done!")
        
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
