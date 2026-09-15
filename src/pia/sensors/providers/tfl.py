"""Transport for London JamCams (~890). JPEG snapshot + a 10 s MP4 clip, refreshed every few minutes."""
from pia.sensors.base import CameraProvider, CameraSpec
from pia.sensors.http import get

LIST_URL = "https://api.tfl.gov.uk/Place/Type/JamCam"


class TfLJamCams(CameraProvider):
    provider_id = "tfl"
    attribution = "Powered by TfL Open Data (Transport for London)"
    default_refresh_seconds = 180

    def list_cameras(self):
        r = get(LIST_URL, timeout=90)
        r.raise_for_status()
        cams = []
        for place in r.json():
            props = {p.get("key"): p.get("value") for p in place.get("additionalProperties", [])}
            image, video = props.get("imageUrl"), props.get("videoUrl")
            lat, lon = place.get("lat"), place.get("lon")
            if not image or not self.valid(lat, lon):
                continue
            cams.append(CameraSpec(
                external_id=place.get("id") or image,
                name=place.get("commonName") or "JamCam",
                lat=float(lat), lon=float(lon),
                media_url=image,
                media_kind="SNAPSHOT",
                video_url=video,
                refresh_seconds=self.default_refresh_seconds,
                city="London", country_code="GB",
                metadata={"available": props.get("available"), "view": props.get("view")},
            ))
        return cams
