"""
Runs the structured connectors on a schedule (OpenSanctions nightly). Other connectors register here.
"""
import os
import time

from loguru import logger

from pia.connectors.base import Ingestor
from pia.connectors.opensanctions import OpenSanctionsConnector
from pia.core.base_agent import BaseAgent
from pia.core.database import DatabaseManager
from pia.kg.resolver import Resolver


class ConnectorAgent(BaseAgent):
    EVERY_SEC = int(os.getenv("CONNECTORS_EVERY_SEC", str(24 * 3600)))
    DATASETS = [d for d in os.getenv("OPENSANCTIONS_DATASETS", "sanctions").split(",") if d]

    def setup(self):
        self.db = DatabaseManager()
        self.ingestor = Ingestor(self.db, Resolver(self.db))
        self._last = 0.0
        logger.info(f"{self.name} ready (OpenSanctions: {self.DATASETS}, every {self.EVERY_SEC}s)")

    def poll(self):
        if time.time() - self._last < self.EVERY_SEC:
            return
        for ds in self.DATASETS:
            try:
                self.ingestor.run(OpenSanctionsConnector(self.db, ds))
            except Exception as e:
                logger.error(f"opensanctions {ds}: {e}")
        self._last = time.time()

    def stop(self):
        self.db.close()


if __name__ == "__main__":
    ConnectorAgent(name="connectors_v1", interval_sec=600).run()
