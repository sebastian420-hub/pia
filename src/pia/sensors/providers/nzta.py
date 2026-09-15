"""NZ Transport Agency traffic cameras (~310). XML list, JPEG snapshots."""
import xml.etree.ElementTree as ET

from pia.sensors.base import CameraProvider, CameraSpec
from pia.sensors.http import get

LIST_URL = "https://trafficnz.info/service/traffic/rest/4/cameras/all"
IMAGE_BASE = "https://trafficnz.info"


class NZTA(CameraProvider):
    provider_id = "nzta"
    attribution = "NZ Transport Agency Waka Kotahi (trafficnz.info)"
    default_refresh_seconds = 120

    def list_cameras(self):
        r = get(LIST_URL)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        cams = []
        for cam in root.iter("camera"):
            g = lambda tag: (cam.findtext(tag) or "").strip()
            lat, lon = g("latitude"), g("longitude")
            image = g("imageUrl")
            if not image or not self.valid(lat, lon):
                continue
            if image.startswith("/"):
                image = IMAGE_BASE + image
            cams.append(CameraSpec(
                external_id=g("id") or image,
                name=g("name") or g("description") or "NZTA camera",
                lat=float(lat), lon=float(lon),
                media_url=image,
                refresh_seconds=self.default_refresh_seconds,
                city=g("region") or None, country_code="NZ",
                metadata={"description": g("description"), "direction": g("direction")},
            ))
        return cams
