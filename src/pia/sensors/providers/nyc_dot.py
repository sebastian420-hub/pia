"""
NYC DOT traffic cameras (~900). Photo every ~2 s. The API only answers US IPs, so this
provider goes through the US relay and is ON_DEMAND (visible only during a live session).
Field names from public documentation; not verifiable from outside the US.
"""
from pia.sensors.base import CameraProvider, CameraSpec
from pia.sensors.http import get

LIST_URL = "https://webcams.nyctmc.org/api/cameras"
IMAGE_URL = "https://webcams.nyctmc.org/api/cameras/{id}/image"


class NYCDOT(CameraProvider):
    provider_id = "nyc_dot"
    attribution = "NYC Department of Transportation (nyctmc.org)"
    cost_class = "ON_DEMAND"
    requires_relay = True
    default_refresh_seconds = 5

    def list_cameras(self):
        r = get(LIST_URL, via_relay=True, timeout=60)
        r.raise_for_status()
        cams = []
        for cam in r.json():
            lat, lon = cam.get("latitude"), cam.get("longitude")
            cid = cam.get("id")
            if not cid or not self.valid(lat, lon):
                continue
            cams.append(CameraSpec(
                external_id=str(cid),
                name=cam.get("name") or f"NYC camera {cid}",
                lat=float(lat), lon=float(lon),
                media_url=cam.get("imageUrl") or IMAGE_URL.format(id=cid),
                refresh_seconds=self.default_refresh_seconds,
                city="New York", country_code="US",
                metadata={"isOnline": cam.get("isOnline"), "area": cam.get("area")},
            ))
        return cams
