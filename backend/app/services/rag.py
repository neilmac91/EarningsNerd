import os
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
from app.services.openai_service import OpenAIService
from app.config import settings

class RAGService:
    def __init__(self):
        url: str = settings.SUPABASE_URL
        key: str = settings.SUPABASE_SERVICE_KEY
        
        if url and key:
            # Use supabase-py client
            self.supabase: Optional[Client] = create_client(url, key)
        else:
            print("⚠️ Supabase credentials not found. RAG disabled.")
            self.supabase = None
            
        self.openai_service = OpenAIService()

    async def process_filing(self, filing_id: int, text_content: str) -> bool:
        """
        Chunks the filing text, generates embeddings, and stores in Supabase.
        """
        if not self.supabase:
            return False
            
        print(f"Processing RAG for filing {filing_id}...")
        chunks = self._chunk_text(text_content)
        
        # Process in batches to avoid rate limits
        batch_size = 10
        total_chunks = len(chunks)
        
        for i in range(0, total_chunks, batch_size):
            batch = chunks[i:i + batch_size]
            texts = [c['content'] for c in batch]
            
            try:
                embeddings = await self._get_embeddings(texts)
            except Exception as e:
                print(f"Error generating embeddings: {e}")
                continue
            
            data_to_insert = []
            for j, chunk in enumerate(batch):
                # Ensure we have an embedding for this chunk
                if j < len(embeddings):
                    data_to_insert.append({
                        "filing_id": filing_id,
                        "chunk_index": chunk['index'],
                        "content": chunk['content'],
                        "section_name": chunk.get('section', 'unknown'),
                        "embedding": embeddings[j]
                    })
            
            if data_to_insert:
                try:
                    self.supabase.table("filing_chunks").insert(data_to_insert).execute()
                    print(f"Inserted batch {i//batch_size + 1}/{(total_chunks + batch_size - 1)//batch_size}")
                except Exception as e:
                    print(f"Error inserting chunks to Supabase: {e}")
        
        return True

    async def query_filing(self, filing_id: int, query: str, limit: int = 5) -> str:
        """
        Retrieves relevant chunks and generates an answer.
        """
        if not self.supabase:
            return "RAG Service Unavailable"
            
        # 1. Embed query
        try:
            query_embeddings = await self._get_embeddings([query])
            if not query_embeddings:
                return "Could not understand query."
            embedding_vector = query_embeddings[0]
        except Exception as e:
            print(f"Embedding error: {e}")
            return "Error processing query."
        
        # 2. Vector Search (RPC call to Supabase)
        # Note: You need to create a 'match_filing_chunks' function in Postgres
        params = {
            "query_embedding": embedding_vector, 
            "match_threshold": 0.5, 
            "match_count": limit,
            "filter_filing_id": filing_id
        }
        
        try:
            rpc_response = self.supabase.rpc("match_filing_chunks", params).execute()
            matches = rpc_response.data
        except Exception as e:
            print(f"Vector search error: {e}")
            return "Error retrieving context."

        if not matches:
            return "No relevant information found in this filing."

        # 3. Synthesize
        context = "\n\n".join([f"--- Chunk {m.get('chunk_index', '?')} ---\n{m['content']}" for m in matches])
        
        prompt = f"""
You are an expert financial analyst. Answer the question based ONLY on the provided context from a 10-K/10-Q filing.
If the answer is not in the context, say "I cannot find this information in the filing."

Context:
{context}

Question: {query}

Answer:
"""
        
        return await self.openai_service.get_chat_completion(prompt)

    def _chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 100) -> List[Dict]:
        """
        Simple character splitter with overlap.
        Ideally, use a recursive character splitter or semantic splitter.
        """
        chunks = []
        start = 0
        text_len = len(text)
        
        index = 0
        while start < text_len:
            end = start + chunk_size
            chunk_text = text[start:end]
            
            # Simple section detection (very naive)
            section = "body"
            if "risk factors" in chunk_text.lower()[:100]:
                section = "risk_factors"
            elif "financial" in chunk_text.lower()[:100]:
                section = "financials"
                
            chunks.append({
                "index": index,
                "content": chunk_text,
                "section": section
            })
            
            start += (chunk_size - overlap)
            index += 1
            
        return chunks

    async def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings using OpenAI.
        """
        # Ensure texts are not empty
        texts = [t for t in texts if t.strip()]
        if not texts:
            return []

        try:
            response = await self.openai_service.client.embeddings.create(
                input=texts,
                model="text-embedding-3-small" # Fast and cheap
            )
            return [data.embedding for data in response.data]
        except Exception as e:
            print(f"OpenAI Embedding Error: {e}")
            raise e

