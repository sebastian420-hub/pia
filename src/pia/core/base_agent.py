from abc import ABC, abstractmethod
import json
import socket
import time
from loguru import logger
import signal
import sys

class BaseAgent(ABC):
    """Abstract Base Class for all autonomous PIA agents."""
    
    def __init__(self, name: str, interval_sec: int = 60):
        self.name = name
        self.interval_sec = interval_sec
        self.running = False
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

    def handle_shutdown(self, signum, frame):
        """Gracefully shuts down the agent on interrupt."""
        logger.info(f"Shutdown signal received for {self.name}. Stopping...")
        self.running = False
        self.stop()
        sys.exit(0)

    @abstractmethod
    def setup(self):
        """Initializes dependencies (DB connections, API keys, etc.)."""
        pass

    @abstractmethod
    def poll(self):
        """The main execution logic (fetching and processing data)."""
        pass

    @abstractmethod
    def stop(self):
        """Cleanup logic before exiting."""
        pass

    def heartbeat(self, status: str = "OK", detail: dict = None):
        """Upserts this agent's row in agent_heartbeats (if the agent has a self.db)."""
        db = getattr(self, "db", None)
        if db is None:
            return
        try:
            db.execute_query("""
                INSERT INTO agent_heartbeats (agent_name, agent_kind, hostname, last_beat, status, detail)
                VALUES (%s, %s, %s, NOW(), %s, %s::jsonb)
                ON CONFLICT (agent_name) DO UPDATE SET
                    last_beat = NOW(), status = EXCLUDED.status, detail = EXCLUDED.detail, hostname = EXCLUDED.hostname
            """, (self.name, type(self).__name__, socket.gethostname(), status, json.dumps(detail or {})))
        except Exception as e:  # a missing table must never kill an agent
            logger.debug(f"heartbeat skipped: {e}")

    def run(self):
        """Starts the agent's main execution loop."""
        self.setup()
        self.running = True
        logger.info(f"Agent {self.name} started (Polling every {self.interval_sec}s)")

        while self.running:
            try:
                self.poll()
                self.heartbeat("OK", {"interval_sec": self.interval_sec})
            except Exception as e:
                logger.error(f"Error in {self.name} polling loop: {e}")
                self.heartbeat("ERROR", {"error": str(e)[:500]})
                # Exponential backoff or simple sleep on error
                time.sleep(10)
                continue

            time.sleep(self.interval_sec)
