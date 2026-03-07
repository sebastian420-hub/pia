import asyncio
import os
import sys
import asyncpg
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "pia")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_NAME = os.getenv("DB_NAME", "pia")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# LLM Setup
llm_client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

async def generate_embedding(text):
    try:
        response = await llm_client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None

async def populate():
    print("Connecting to database...")
    conn = await asyncpg.connect(DATABASE_URL)
    
    print("Fetching entities without embeddings...")
    # Get entities that don't have embeddings yet
    # Limit to 500 for safety, can be run multiple times
    query = """
        SELECT entity_id, name, description 
        FROM entities 
        WHERE embedding IS NULL
        LIMIT 500
    """
    records = await conn.fetch(query)
    print(f"Found {len(records)} entities to process.")

    for record in records:
        text_to_embed = f"{record['name']}: {record['description'] or ''}"
        
        embedding = await generate_embedding(text_to_embed)
        
        if embedding:
            embedding_str = f"[{','.join(map(str, embedding))}]"
            update_query = """
                UPDATE entities 
                SET embedding = $1::vector 
                WHERE entity_id = $2
            """
            await conn.execute(update_query, embedding_str, record['entity_id'])
            print(f"✅ Updated {record['name']}")
        
        # Small delay to avoid rate limits
        await asyncio.sleep(0.2)
        
    await conn.close()
    print("Done!")

if __name__ == "__main__":
    asyncio.run(populate())
