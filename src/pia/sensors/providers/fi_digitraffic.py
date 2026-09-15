"""Finland Digitraffic weather cameras (~800 stations, several presets each). GeoJSON, gzip required."""
from pia.sensors.base import CameraProvider, CameraSpec
from pia.sensors.http import get

LIST_URL = "https://tie.digitraffic.fi/api/weathercam/v1/stations"
IMAGE_URL = "https://weathercam.digitraffic.fi/{preset_id}.jpg"


class FinlandDigitraffic(CameraProvider):
    provider_id = "fi_digitraffic"
    attribution = "Fintraffic / digitraffic.fi (CC 4.0 BY)"
    default_refresh_seconds = 600

    def list_cameras(self):
        r = get(LIST_URL, headers={"Digitraffic-User": "PIA-camera-agent"})
        r.raise_for_status()
        cams = []
        for f in r.json().get("features", []):
            props = f.get("properties") or {}
            coords = (f.get("geometry") or {}).get("coordinates") or []
            if len(coords) < 2 or not self.valid(coords[1], coords[0]):
                continue
            presets = props.get("presets") or []
            for preset in presets[:1]:  # one preset per station keeps the layer readable
                pid = preset.get("id")
                if not pid:
                    continue
                cams.append(CameraSpec(
                    external_id=str(pid),
                    name=f"{props.get('name') or props.get('id')} · {preset.get('presentationName') or pid}",
                    lat=float(coords[1]), lon=float(coords[0]),
                    media_url=IMAGE_URL.format(preset_id=pid),
                    refresh_seconds=self.default_refresh_seconds,
                    city=None, country_code="FI",
                    metadata={"station_id": props.get("id"), "presets": len(presets)},
                ))
        return cams
