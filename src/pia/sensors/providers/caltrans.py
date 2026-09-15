"""
Caltrans CCTV (thousands; districts 1-12). JPEG snapshot plus, for many cameras, a live
stream URL. US-only network, so ON_DEMAND via the relay. Field names from the public JSON
schema; not verifiable from outside the US.
"""
from loguru import logger

from pia.sensors.base import CameraProvider, CameraSpec
from pia.sensors.http import get

DISTRICTS = ["d3", "d4", "d5", "d6", "d7", "d8", "d10", "d11", "d12"]  # Sacramento … San Diego
LIST_URL = "https://cwwp2.dot.ca.gov/data/{d}/cctv/cctvStatus{D}.json"


class Caltrans(CameraProvider):
    provider_id = "caltrans"
    attribution = "California Department of Transportation (Caltrans) CWWP"
    cost_class = "ON_DEMAND"
    requires_relay = True
    default_refresh_seconds = 30

    def list_cameras(self):
        cams = []
        for d in DISTRICTS:
            url = LIST_URL.format(d=d, D=d.upper().replace("D", "D0") if len(d) == 2 else d.upper())
            try:
                r = get(url, via_relay=True, timeout=60)
                r.raise_for_status()
                data = r.json().get("data", [])
            except Exception as e:
                logger.warning(f"Caltrans {d}: {e}")
                continue
            for item in data:
                c = item.get("cctv") or {}
                loc, img = c.get("location") or {}, c.get("imageData") or {}
                lat, lon = loc.get("latitude"), loc.get("longitude")
                still = ((img.get("static") or {}).get("currentImageURL") or "").strip()
                stream = (img.get("streamingVideoURL") or "").strip()
                if not still and not stream:
                    continue
                if not self.valid(lat, lon):
                    continue
                cams.append(CameraSpec(
                    external_id=f"{d}:{c.get('index') or loc.get('locationName') or still}",
                    name=loc.get("locationName") or "Caltrans camera",
                    lat=float(lat), lon=float(lon),
                    media_url=still or stream,
                    media_kind="SNAPSHOT" if still else "HLS",
                    video_url=stream or None,
                    refresh_seconds=self.default_refresh_seconds,
                    city=loc.get("nearbyPlace") or loc.get("county"), country_code="US",
                    metadata={"district": loc.get("district"), "route": loc.get("route"), "inService": c.get("inService")},
                ))
        return cams
