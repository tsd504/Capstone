"""
Simple RAG System

"""

from pathlib import Path
import pandas as pd
import json
import os
from datetime import datetime

# Google Cloud imports
from google.cloud import bigquery
import vertexai
from vertexai.preview.language_models import TextEmbeddingModel
import google.generativeai as genai

class SimpleRAG:
    def __init__(self, project_id, gemini_api_key):
        """
        Initialize the simple RAG system
        """
        self.project_id = project_id
        
        # Service account credentials needed to access bigquery and vertex ai
        credentials_path = Path(__file__).parent / 'credentials.json'
        if credentials_path.exists():
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(credentials_path)
            print("Using credentials.json file")
        else:
            print("Warning: credentials.json not found. Make sure it's in the same directory as this script.")
        
        # Initialize BigQuery
        self.bq_client = bigquery.Client(project=project_id)
        
        # Initialize Vertex AI
        vertexai.init(project=project_id, location="us-central1")
        
        # Initialize embedding model
        self.embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-005")
        print("Vertex AI embedding model ready")
        
        # Initialize Gemini
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
        """
        Process a CSV file and store embeddings in BigQuery
        """
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
    
    def query(self, question, top_k=3):
        """
        Query the RAG system
        """
        print(f"Querying: {question}")
        
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
        
        # Generate response with Gemini
        prompt = f"""
        Based on this information, answer the question. If the information doesn't contain the answer, say so.

        Information:
        {context}

        Question: {question}

        Answer:
        """
        
        response = self.gemini_model.generate_content(prompt)
        return response.text


def main():
    """
    Main function - just run this!
    """
    print("=== Simple RAG System ===")
    print()
    
    # STEP 1: Update these values
    PROJECT_ID = "rag-project-469419"  # Your Google Cloud project ID
    GEMINI_API_KEY = "AIzaSyC1xkqjimA7P8Yus0iXUoLkUgSxza1sbNs"  # Your Gemini API key
    
    # STEP 2: Make sure your CSV files are in the right place
    # Use Path(__file__).parent to reference relative to script location
    script_dir = Path(__file__).parent
    CSV_FILES = [
        #script_dir.parent / "scraper" / "items_combined.csv",
        script_dir.parent / "scraper" / "quests_combined.csv"
    ]
    
    try:
        # Create RAG system
        print("Setting up RAG system...")
        rag = SimpleRAG(PROJECT_ID, GEMINI_API_KEY)
        print("RAG system ready!")
        print()
        
        # Process CSV files
        print("Processing CSV files...")
        for csv_file in CSV_FILES:
            if csv_file.exists():
                rag.process_csv(str(csv_file))
                print()
            else:
                print(f"File not found: {csv_file}")
        print()
        
        # Test some queries
        prompt = input("Prompt: ")
        while prompt.lower() != "exit":
            print(f"\nQ: {prompt}")
            answer = rag.query(prompt)
            print(f"A: {answer}")
            print("-" * 50)
            prompt = input("Prompt: ")
        
        print("\nAll done!")
        
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
