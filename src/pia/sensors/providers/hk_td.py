"""Hong Kong Transport Department traffic snapshot cameras (~1,000). UTF-16 TSV list, JPEG every ~2 min."""
import csv
import io

from pia.sensors.base import CameraProvider, CameraSpec
from pia.sensors.http import get

LIST_URL = "https://static.data.gov.hk/td/traffic-snapshot-images/code/Traffic_Camera_Locations_En.csv"


class HongKongTD(CameraProvider):
    provider_id = "hk_td"
    attribution = "Transport Department, HKSAR Government (data.gov.hk)"
    default_refresh_seconds = 120

    def list_cameras(self):
        r = get(LIST_URL)
        r.raise_for_status()
        text = r.content.decode("utf-16").lstrip("\ufeff")  # double BOM: one for UTF-16, one inside
        rows = csv.DictReader(io.StringIO(text), delimiter="\t")
        cams = []
        for row in rows:
            key = (row.get("key") or "").strip()
            lat, lon, url = row.get("latitude"), row.get("longitude"), (row.get("url") or "").strip()
            if not key or not url or not self.valid(lat, lon):
                continue
            cams.append(CameraSpec(
                external_id=key,
                name=(row.get("description") or key).strip(),
                lat=float(lat), lon=float(lon),
                media_url=url,
                refresh_seconds=self.default_refresh_seconds,
                city="Hong Kong", country_code="HK",
                metadata={"district": row.get("district"), "region": row.get("region")},
            ))
        return cams
