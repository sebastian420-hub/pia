"""Singapore LTA traffic images via data.gov.sg (~90). JPEG with a timestamp; the image URL changes every refresh."""
from pia.sensors.base import CameraProvider, CameraSpec
from pia.sensors.http import get

LIST_URL = "https://api.data.gov.sg/v1/transport/traffic-images"


class SingaporeLTA(CameraProvider):
    provider_id = "sg_lta"
    attribution = "Land Transport Authority, Singapore (data.gov.sg, Singapore Open Data Licence)"
    default_refresh_seconds = 60

    def list_cameras(self):
        r = get(LIST_URL)
        r.raise_for_status()
        items = r.json().get("items") or []
        cams = []
        for cam in (items[0].get("cameras") if items else []) or []:
            loc = cam.get("location") or {}
            lat, lon = loc.get("latitude"), loc.get("longitude")
            if not cam.get("image") or not self.valid(lat, lon):
                continue
            cams.append(CameraSpec(
                external_id=str(cam.get("camera_id")),
                name=f"LTA camera {cam.get('camera_id')}",
                lat=float(lat), lon=float(lon),
                # The image URL rotates; the agent stores the list URL as media_url and the
                # snapshot proxy resolves the current image by camera_id (see resolve_snapshot).
                media_url=f"{LIST_URL}#camera_id={cam.get('camera_id')}",
                refresh_seconds=self.default_refresh_seconds,
                city="Singapore", country_code="SG",
                metadata={"last_image": cam.get("image"), "timestamp": cam.get("timestamp")},
            ))
        return cams

    @staticmethod
    def resolve_snapshot(camera_id: str) -> str:
        """Returns the current image URL for one camera (the URL changes on every refresh)."""
        r = get(LIST_URL, timeout=20)
        r.raise_for_status()
        items = r.json().get("items") or []
        for cam in (items[0].get("cameras") if items else []) or []:
            if str(cam.get("camera_id")) == str(camera_id):
                return cam.get("image") or ""
        return ""
