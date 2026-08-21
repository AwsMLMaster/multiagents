"""
Geocoding Integration.

Resolves free-text US locations (city, ZIP, address, neighborhood) to
coordinates, and computes distance/commute-time estimates between points.
Supports Google Maps or Mapbox as the underlying provider.
"""

import logging
import math
from dataclasses import dataclass
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class GeocodingConfig:
    """Configuration for the geocoding client."""
    provider: str = "google"  # google, mapbox
    api_key: str = ""
    timeout: int = 10


@dataclass
class GeoLocation:
    """A resolved geographic location."""
    query: str
    formatted_address: str
    latitude: float
    longitude: float
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None


@dataclass
class CommuteEstimate:
    """Estimated commute between two locations."""
    origin: str
    destination: str
    distance_miles: float
    driving_minutes: Optional[float] = None
    transit_minutes: Optional[float] = None


class GeocodingError(Exception):
    """Raised when geocoding fails."""
    pass


class GeocodingClient:
    """
    Client for resolving locations and estimating commute times.
    """

    def __init__(self, config: GeocodingConfig):
        self.config = config

    async def geocode(self, location: str) -> Optional[GeoLocation]:
        """
        Resolve a free-text location to coordinates.

        Args:
            location: Address, city, ZIP code, or neighborhood name.

        Returns:
            GeoLocation if resolved, else None.
        """
        if not self.config.api_key:
            logger.warning("Geocoding API key not configured, cannot resolve location")
            return None

        try:
            if self.config.provider == "mapbox":
                return await self._geocode_mapbox(location)
            return await self._geocode_google(location)
        except GeocodingError as e:
            logger.warning(f"Geocoding failed for '{location}': {e}")
            return None

    async def _geocode_google(self, location: str) -> Optional[GeoLocation]:
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {"address": f"{location}, USA", "key": self.config.api_key}

        timeout = aiohttp.ClientTimeout(total=self.config.timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    raise GeocodingError(f"Google geocoding returned status {resp.status}")
                data = await resp.json()

        results = data.get("results", [])
        if not results:
            return None

        result = results[0]
        loc = result["geometry"]["location"]

        components = {c["types"][0]: c["long_name"] for c in result.get("address_components", []) if c.get("types")}

        return GeoLocation(
            query=location,
            formatted_address=result.get("formatted_address", location),
            latitude=loc["lat"],
            longitude=loc["lng"],
            city=components.get("locality"),
            state=components.get("administrative_area_level_1"),
            zip_code=components.get("postal_code"),
        )

    async def _geocode_mapbox(self, location: str) -> Optional[GeoLocation]:
        url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{location}.json"
        params = {"access_token": self.config.api_key, "country": "us", "limit": 1}

        timeout = aiohttp.ClientTimeout(total=self.config.timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    raise GeocodingError(f"Mapbox geocoding returned status {resp.status}")
                data = await resp.json()

        features = data.get("features", [])
        if not features:
            return None

        feature = features[0]
        lng, lat = feature["center"]

        return GeoLocation(
            query=location,
            formatted_address=feature.get("place_name", location),
            latitude=lat,
            longitude=lng,
        )

    def haversine_distance_miles(
        self, lat1: float, lng1: float, lat2: float, lng2: float
    ) -> float:
        """Calculate great-circle distance between two points in miles."""
        radius_miles = 3958.8
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        d_phi = math.radians(lat2 - lat1)
        d_lambda = math.radians(lng2 - lng1)

        a = (
            math.sin(d_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return radius_miles * c

    async def estimate_commute(
        self, origin: str, destination: str
    ) -> Optional[CommuteEstimate]:
        """
        Estimate commute distance/time between two locations.

        Note: without a routing API key configured, only straight-line
        distance is returned; driving/transit minutes are left unset.
        """
        origin_loc = await self.geocode(origin)
        dest_loc = await self.geocode(destination)

        if not origin_loc or not dest_loc:
            return None

        distance = self.haversine_distance_miles(
            origin_loc.latitude, origin_loc.longitude,
            dest_loc.latitude, dest_loc.longitude,
        )

        # Rough driving time heuristic (avg 30mph incl. traffic/lights) as a
        # fallback when no routing API is configured.
        estimated_driving_minutes = (distance / 30.0) * 60

        return CommuteEstimate(
            origin=origin,
            destination=destination,
            distance_miles=round(distance, 1),
            driving_minutes=round(estimated_driving_minutes, 1),
        )


def create_geocoding_client(
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
) -> GeocodingClient:
    """Factory function to create a configured geocoding client."""
    config = GeocodingConfig(
        provider=provider or "google",
        api_key=api_key or "",
    )
    return GeocodingClient(config)
