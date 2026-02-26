from abc import ABC, abstractmethod
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

    def run(self):
        """Starts the agent's main execution loop."""
        self.setup()
        self.running = True
        logger.info(f"Agent {self.name} started (Polling every {self.interval_sec}s)")
        
        while self.running:
            try:
                self.poll()
            except Exception as e:
                logger.error(f"Error in {self.name} polling loop: {e}")
                # Exponential backoff or simple sleep on error
                time.sleep(10)
                continue
            
            time.sleep(self.interval_sec)
