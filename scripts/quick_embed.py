import asyncio
import os
import asyncpg
from openai import AsyncOpenAI

DB_HOST = "postgres"
DB_PORT = "5432"
DB_USER = "pia"
DB_PASSWORD = "password"
DB_NAME = "pia"

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

llm_client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY", "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"),
)

async def generate_embedding(text):
    try:
        response = await llm_client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error: {e}")
        return None

async def main():
    conn = await asyncpg.connect(DATABASE_URL)
    records = await conn.fetch("SELECT entity_id, name, description FROM entities WHERE watch_status = 'ACTIVE' AND embedding IS NULL")
    
    print(f"Found {len(records)} entities to embed.")
    for r in records:
        text = f"{r['name']}: {r['description']}"
        print(f"Embedding {r['name']}...")
        emb = await generate_embedding(text)
        if emb:
            emb_str = f"[{','.join(map(str, emb))}]"
            await conn.execute("UPDATE entities SET embedding = $1::vector WHERE entity_id = $2", emb_str, r['entity_id'])
            
    await conn.close()
    print("Done")

if __name__ == "__main__":
    asyncio.run(main())
