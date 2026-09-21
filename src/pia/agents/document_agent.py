import json
import os
import hashlib
import fitz  # PyMuPDF
from loguru import logger

from pia.core.base_agent import BaseAgent
from pia.core.database import DatabaseManager
from pia.core.text import chunk_text

class DocumentAgent(BaseAgent):
    """
    Ingests static documents (PDF/TXT), chunks them, and injects them into the UIR spine
    as HUMINT for Deep Document Exploitation.
    """

    def setup(self):
        self.db = DatabaseManager()
        self.ingestor = None          # built on the first SPOTREP
        self.doc_dir = os.getenv("DOC_DIR", "/app/data/documents")
        
        if not os.path.exists(self.doc_dir):
            os.makedirs(self.doc_dir, exist_ok=True)
            logger.info(f"Created document directory: {self.doc_dir}")
            
        logger.info(f"{self.name} initialized. Monitoring {self.doc_dir} for documents.")

    def poll(self):
        """Scans the directory for new documents."""
        for filename in os.listdir(self.doc_dir):
            filepath = os.path.join(self.doc_dir, filename)
            
            if not os.path.isfile(filepath) or filename.endswith(".meta.json"):
                continue
                
            if filename.lower().endswith('.pdf'):
                self.process_pdf(filepath, filename)
            elif filename.lower().endswith(('.txt', '.md', '.json')):
                self.process_txt(filepath, filename)

    def process_pdf(self, filepath: str, filename: str):
        """Extracts text from a PDF and injects chunks into the database."""
        try:
            doc = fitz.open(filepath)
            full_text = ""
            for page in doc:
                full_text += page.get_text("text") + "\n"
            doc.close()

            outcome = self._inject_chunks(full_text, filename)
            self._mark_processed(filepath, filename, outcome)

        except Exception as e:
            logger.error(f"Failed to process PDF {filename}: {e}")
            self._mark_processed(filepath, filename, "failed")

    def process_txt(self, filepath: str, filename: str):
        """Reads text from a TXT file and injects chunks into the database."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                full_text = f.read()

            # a SPOTREP (fixed human-report format) is read deterministically; anything else is chunked for the analyst
            head = full_text.lstrip()[:400].lower()
            if head.startswith('reporter:') or (head.startswith('{') and '"reporter"' in head):
                outcome = self._ingest_spotrep(full_text, filename)
            else:
                outcome = self._inject_chunks(full_text, filename)
            self._mark_processed(filepath, filename, outcome)

        except Exception as e:
            logger.error(f"Failed to process TXT {filename}: {e}")
            self._mark_processed(filepath, filename, "failed")

    def _ingest_spotrep(self, text: str, filename: str) -> str:
        from pia.connectors.spotrep import SpotrepConnector, SpotrepError, parse
        try:
            rep = parse(text)
        except (SpotrepError, ValueError) as e:
            logger.error(f"SPOTREP {filename} rejected: {e}")
            return "failed"
        mission_id = None
        if rep.mission:
            row = self.db.execute_query("SELECT mission_id FROM missions WHERE name = %s OR mission_id::text = %s LIMIT 1",
                                        (rep.mission, rep.mission), fetch=True)
            mission_id = str(row[0]["mission_id"]) if row else None
        if self.ingestor is None:
            from pia.connectors.base import Ingestor
            from pia.kg.resolver import Resolver
            self.ingestor = Ingestor(self.db, Resolver(self.db))
        connector = SpotrepConnector(rep, f"spotrep:{filename}", mission_id)
        stats = self.ingestor.run(connector)
        # the uploader may read what they uploaded: a grant on the (restricted) reporter source
        meta = self._meta(filename)
        if meta.get("uploaded_by"):
            self.db.execute_query("""
                INSERT INTO source_grants (source_id, user_id) VALUES (%s, %s::uuid) ON CONFLICT DO NOTHING
            """, (connector.source["source_id"], meta["uploaded_by"]))
        logger.success(f"SPOTREP {filename} from {rep.reporter}: {stats}")
        return "processed"

    def _meta(self, filename: str) -> dict:
        """The upload's sidecar (who uploaded it), if the API wrote one."""
        p = os.path.join(self.doc_dir, filename + ".meta.json")
        try:
            with open(p) as f:
                return json.load(f)
        except Exception:
            return {}

    def _inject_chunks(self, full_text: str, filename: str) -> str:
        """
        Chunks the text and injects each chunk as a unique HUMINT record.
        Returns 'processed' (something was stored or already existed) or 'failed'
        (nothing could be stored) so the caller does not silently discard the file.
        """
        # Clean text
        clean_text = " ".join(full_text.split())
        if not clean_text:
            logger.warning(f"No text extracted from {filename}")
            return "failed"

        chunks = chunk_text(clean_text)
        logger.info(f"Extracted {len(chunks)} chunks from {filename}")

        inserted_count = 0
        existing_count = 0
        failed_count = 0
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
                existing_count += 1
                continue

            headline = f"Document Extract: {filename} (Part {i+1}/{len(chunks)})"
            
            # We enforce the INVESTIGATIVE mission category directly via domain/priority
            try:
                self.db.execute_query(
                    """
                    INSERT INTO intelligence_records (
                        source_type, source_id, source_agent, source_name, content_hash,
                        content_headline, content_raw, body_status, domain, priority, confidence
                    ) VALUES (
                        'HUMINT', 'upload', %s, %s, %s,
                        %s, %s, 'OK', 'INVESTIGATIVE', 'HIGH', 0.80
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
                failed_count += 1
                logger.error(f"Failed to insert chunk {i} from {filename}: {e}")

        if inserted_count > 0:
            logger.success(f"Injected {inserted_count} new UIRs from {filename} into the pipeline.")
        if failed_count and not inserted_count and not existing_count:
            logger.error(f"Every chunk of {filename} failed to insert ({failed_count}); moving it to failed/")
            return "failed"
        return "processed"

    def _mark_processed(self, filepath: str, filename: str, outcome: str = "processed"):
        """Moves the file to 'processed/' or 'failed/' so it is neither re-read nor lost."""
        target_dir = os.path.join(self.doc_dir, "failed" if outcome == "failed" else "processed")
        os.makedirs(target_dir, exist_ok=True)
        new_path = os.path.join(target_dir, filename)
        if os.path.exists(new_path):
            base, ext = os.path.splitext(filename)
            new_path = os.path.join(target_dir, f"{base}_{hashlib.sha1(filepath.encode()).hexdigest()[:8]}{ext}")
        os.rename(filepath, new_path)
        if os.path.exists(filepath + ".meta.json"):
            os.rename(filepath + ".meta.json", new_path + ".meta.json")
        logger.info(f"Archived {filename} to {os.path.basename(target_dir)}/")

    def stop(self):
        self.db.close()

if __name__ == "__main__":
    agent = DocumentAgent(name="deep_doc_exploiter_v1", interval_sec=30)
    agent.run()
