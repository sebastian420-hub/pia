"""
OpenSanctions connector: sanctions, PEPs and watchlists from 463 official sources, as FtM.
Free for non-commercial use (commercial use needs a licence: https://www.opensanctions.org/licensing/).
"""
import os
from datetime import datetime
from typing import Iterable, Optional

import requests
from loguru import logger

from pia.connectors.base import Connector, Item
from pia.connectors.ftm import ftm_items

DATASETS = {
    "sanctions": "https://data.opensanctions.org/datasets/latest/sanctions/entities.ftm.json",
    "peps": "https://data.opensanctions.org/datasets/latest/peps/entities.ftm.json",
}


class OpenSanctionsConnector(Connector):
    def __init__(self, db, dataset: str = "sanctions", path: Optional[str] = None):
        self.dataset = dataset
        self.path = path or os.getenv("OPENSANCTIONS_FILE")
        self.source = {"source_id": f"opensanctions_{dataset}", "label": f"OpenSanctions · {dataset}", "kind": "DATASET",
                       "trust": 0.95, "homepage": "https://www.opensanctions.org"}
        rows = db.execute_query("SELECT metadata->>'iso2' AS iso2, qid FROM entities WHERE kind = 'COUNTRY' AND metadata ? 'iso2'", fetch=True) or []
        self.iso2 = {r["iso2"].upper(): r["qid"] for r in rows if r["iso2"]}

    def _lines(self) -> Iterable[str]:
        if self.path:
            with open(self.path, encoding="utf-8") as f:
                for line in f:
                    yield line
            return
        url = DATASETS[self.dataset]
        logger.info(f"streaming {url}")
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            for line in r.iter_lines(decode_unicode=True):
                if line:
                    yield line

    def pull(self, since: Optional[datetime] = None) -> Iterable[Item]:
        return ftm_items(self._lines(), self.iso2)
