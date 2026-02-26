from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class SeismicGeometry(BaseModel):
    """Represents the GeoJSON Point geometry for a seismic event."""
    type: str = "Point"
    coordinates: List[float]  # [longitude, latitude, depth_km]

class SeismicProperties(BaseModel):
    """Critical properties from the USGS GeoJSON feature."""
    mag: Optional[float] = None
    place: Optional[str] = None
    time: int  # Unix timestamp in milliseconds
    updated: int
    tz: Optional[int] = None
    url: str
    detail: Optional[str] = None
    felt: Optional[int] = 0
    cdi: Optional[float] = None
    mmi: Optional[float] = None
    alert: Optional[str] = None
    status: str
    tsunami: int
    sig: int
    net: str
    code: str
    ids: str
    sources: str
    types: str
    nst: Optional[int] = None
    dmin: Optional[float] = None
    rms: Optional[float] = None
    gap: Optional[float] = None
    magType: str
    type: str
    title: str

class SeismicEvent(BaseModel):
    """The unified model for a single seismic event feature."""
    id: str = Field(..., alias="id")  # This maps to our usgs_id
    properties: SeismicProperties
    geometry: SeismicGeometry

    @property
    def event_time(self) -> datetime:
        """Converts the USGS Unix millisecond timestamp to a Python datetime."""
        return datetime.fromtimestamp(self.properties.time / 1000.0)

    @property
    def lon(self) -> float:
        return self.geometry.coordinates[0]

    @property
    def lat(self) -> float:
        return self.geometry.coordinates[1]

    @property
    def depth(self) -> float:
        return self.geometry.coordinates[2]
