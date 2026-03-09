import os
import time
import hashlib
import fitz  # PyMuPDF
from loguru import logger
from datetime import datetime

from pia.core.base_agent import BaseAgent
from pia.core.database import DatabaseManager

class DocumentAgent(BaseAgent):
    """
    Ingests static documents (PDF/TXT), chunks them, and injects them into the UIR spine
    as HUMINT for Deep Document Exploitation.
    """

    def setup(self):
        self.db = DatabaseManager()
        self.doc_dir = os.getenv("DOC_DIR", "/app/data/documents")
        
        if not os.path.exists(self.doc_dir):
            os.makedirs(self.doc_dir, exist_ok=True)
            logger.info(f"Created document directory: {self.doc_dir}")
            
        logger.info(f"{self.name} initialized. Monitoring {self.doc_dir} for documents.")

    def poll(self):
        """Scans the directory for new documents."""
        for filename in os.listdir(self.doc_dir):
            filepath = os.path.join(self.doc_dir, filename)
            
            if not os.path.isfile(filepath):
                continue
                
            if filename.lower().endswith('.pdf'):
                self.process_pdf(filepath, filename)
            elif filename.lower().endswith('.txt'):
                self.process_txt(filepath, filename)

    def _chunk_text(self, text: str, chunk_size: int = 1500, overlap: int = 200) -> list:
        """Splits text into overlapping chunks for context preservation."""
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start += chunk_size - overlap
            
        return chunks

    def process_pdf(self, filepath: str, filename: str):
        """Extracts text from a PDF and injects chunks into the database."""
        try:
            doc = fitz.open(filepath)
            full_text = ""
            for page in doc:
                full_text += page.get_text("text") + "\n"
            doc.close()

            self._inject_chunks(full_text, filename)
            
            # Move to processed folder to prevent infinite looping
            self._mark_processed(filepath, filename)
            
        except Exception as e:
            logger.error(f"Failed to process PDF {filename}: {e}")

    def process_txt(self, filepath: str, filename: str):
        """Reads text from a TXT file and injects chunks into the database."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                full_text = f.read()
            
            self._inject_chunks(full_text, filename)
            self._mark_processed(filepath, filename)
            
        except Exception as e:
            logger.error(f"Failed to process TXT {filename}: {e}")

    def _inject_chunks(self, full_text: str, filename: str):
        """Chunks the text and injects each chunk as a unique HUMINT record."""
        # Clean text
        clean_text = " ".join(full_text.split())
        if not clean_text:
            logger.warning(f"No text extracted from {filename}")
            return

        chunks = self._chunk_text(clean_text)
        logger.info(f"Extracted {len(chunks)} chunks from {filename}")

        inserted_count = 0
        for i, chunk in enumerate(chunks):
            # Create a unique hash for this specific chunk
            chunk_hash = hashlib.sha256(chunk.encode('utf-8')).hexdigest()
            
            # Idempotency Check
            exists = self.db.execute_query(
                "SELECT 1 FROM intelligence_records WHERE content_hash = %s", 
                (chunk_hash,), 
                fetch=True
            )
            if exists:
                continue

            headline = f"Document Extract: {filename} (Part {i+1}/{len(chunks)})"
            
            # We enforce the INVESTIGATIVE mission category directly via domain/priority
            try:
                self.db.execute_query(
                    """
                    INSERT INTO intelligence_records (
                        source_type, source_agent, source_name, content_hash,
                        content_headline, content_raw, domain, priority, confidence
                    ) VALUES (
                        'HUMINT', %s, %s, %s,
                        %s, %s, 'INVESTIGATIVE', 'HIGH', 0.80
                    ) ON CONFLICT (content_hash) DO NOTHING;
                    """,
                    (
                        self.name, 
                        filename, 
                        chunk_hash,
                        headline, 
                        chunk
                    )
                )
                inserted_count += 1
            except Exception as e:
                logger.error(f"Failed to insert chunk {i} from {filename}: {e}")

        if inserted_count > 0:
            logger.success(f"Injected {inserted_count} new UIRs from {filename} into the pipeline.")

    def _mark_processed(self, filepath: str, filename: str):
        """Moves the file to a 'processed' directory."""
        processed_dir = os.path.join(self.doc_dir, "processed")
        os.makedirs(processed_dir, exist_ok=True)
        new_path = os.path.join(processed_dir, filename)
        os.rename(filepath, new_path)
        logger.info(f"Archived {filename} to processed directory.")

    def stop(self):
        self.db.close()

if __name__ == "__main__":
    agent = DocumentAgent(name="deep_doc_exploiter_v1", interval_sec=30)
    agent.run()
