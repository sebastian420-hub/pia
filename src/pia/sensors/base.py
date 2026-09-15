"""
Common shape every camera provider produces. Providers only know how to turn one
city's open-data feed into a list of CameraSpec; the agent does the storing.
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class CameraSpec:
    external_id: str
    name: str
    lat: float
    lon: float
    media_url: str
    media_kind: str = "SNAPSHOT"            # SNAPSHOT | HLS | MP4 | MJPEG
    video_url: Optional[str] = None
    refresh_seconds: int = 60
    city: Optional[str] = None
    country_code: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class CameraProvider:
    """Subclass and implement list_cameras(). Keep providers small and stateless."""

    provider_id: str = ""
    attribution: str = ""
    cost_class: str = "FREE"                # FREE | ON_DEMAND | SUBSCRIPTION
    requires_relay: bool = False
    default_refresh_seconds: int = 60

    def list_cameras(self) -> List[CameraSpec]:
        raise NotImplementedError

    @staticmethod
    def valid(lat, lon) -> bool:
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            return False
        return -90 <= lat <= 90 and -180 <= lon <= 180 and not (lat == 0 and lon == 0)
