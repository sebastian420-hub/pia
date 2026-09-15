"""City of Toronto RESCU traffic cameras (~340). CKAN GeoJSON, JPEG snapshots."""
from pia.sensors.base import CameraProvider, CameraSpec
from pia.sensors.http import get

PACKAGE_URL = "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/package_show?id=traffic-cameras"


class Toronto(CameraProvider):
    provider_id = "toronto"
    attribution = "City of Toronto Open Data (Open Government Licence – Toronto)"
    default_refresh_seconds = 120

    def list_cameras(self):
        pkg = get(PACKAGE_URL)
        pkg.raise_for_status()
        resources = pkg.json()["result"]["resources"]
        geojson_url = next(r["url"] for r in resources if r["name"].endswith("4326.geojson"))
        r = get(geojson_url, timeout=90)
        r.raise_for_status()
        cams = []
        for f in r.json().get("features", []):
            p = f.get("properties") or {}
            coords = (f.get("geometry") or {}).get("coordinates") or []
            # MultiPoint [[lon, lat]] or Point [lon, lat]
            if coords and isinstance(coords[0], list):
                coords = coords[0]
            if len(coords) < 2 or not self.valid(coords[1], coords[0]) or not p.get("IMAGEURL"):
                continue
            cams.append(CameraSpec(
                external_id=str(p.get("_id") or p.get("IMAGEURL")),
                name=f"{p.get('MAINROAD') or ''} / {p.get('CROSSROAD') or ''}".strip(" /") or "Toronto camera",
                lat=float(coords[1]), lon=float(coords[0]),
                media_url=p["IMAGEURL"],
                refresh_seconds=self.default_refresh_seconds,
                city="Toronto", country_code="CA",
            ))
        return cams
