"""
Property Listings & Public Records Data Integration.

Provides a provider-agnostic client for property search, details, valuation
(AVM), comparable sales, tax assessment, and price history data. Designed to
work against providers such as ATTOM Data, Realtor.com (via RapidAPI), or an
MLS Grid / IDX feed - the HTTP layer is abstracted so a provider can be
swapped via configuration without touching calling code.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class PropertyDataConfig:
    """Configuration for the property data client."""
    provider: str = "attom"
    base_url: str = ""
    api_key: str = ""
    timeout: int = 15
    max_retries: int = 3


@dataclass
class Property:
    """A single property listing / record."""
    property_id: str
    address: str
    city: str
    state: str
    zip_code: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    list_price: Optional[float] = None
    property_type: str = "single_family"  # single_family, condo, townhouse, multi_family, land
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    sqft: Optional[int] = None
    lot_sqft: Optional[int] = None
    year_built: Optional[int] = None
    status: str = "active"  # active, pending, sold, off_market
    days_on_market: Optional[int] = None
    photos: List[str] = field(default_factory=list)
    description: Optional[str] = None
    features: List[str] = field(default_factory=list)
    hoa_fee: Optional[float] = None
    listing_agent: Optional[Dict[str, str]] = None
    price_history: List[Dict[str, Any]] = field(default_factory=list)
    tax_history: List[Dict[str, Any]] = field(default_factory=list)

    def to_summary(self) -> Dict[str, Any]:
        """Compact dict representation for agent responses."""
        return {
            "property_id": self.property_id,
            "address": f"{self.address}, {self.city}, {self.state} {self.zip_code}",
            "list_price": self.list_price,
            "property_type": self.property_type,
            "bedrooms": self.bedrooms,
            "bathrooms": self.bathrooms,
            "sqft": self.sqft,
            "status": self.status,
            "days_on_market": self.days_on_market,
        }


@dataclass
class ValuationEstimate:
    """Automated valuation model (AVM) estimate."""
    property_id: str
    estimated_value: float
    value_range_low: float
    value_range_high: float
    confidence_score: float  # 0.0 - 1.0
    last_updated: datetime
    comparable_count: int = 0


@dataclass
class ComparableSale:
    """A comparable recently-sold property."""
    property_id: str
    address: str
    sale_price: float
    sale_date: datetime
    sqft: Optional[int]
    bedrooms: Optional[int]
    bathrooms: Optional[float]
    distance_miles: float


class PropertyDataError(Exception):
    """Raised when the property data provider request fails."""
    pass


class PropertyDataClient:
    """
    Provider-agnostic client for property listings and public records data.
    """

    def __init__(self, config: PropertyDataConfig):
        self.config = config

    async def _request(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make an authenticated HTTP GET request to the configured provider."""
        url = f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}"
        headers = {"Accept": "application/json"}
        if self.config.api_key:
            headers["apikey"] = self.config.api_key

        timeout = aiohttp.ClientTimeout(total=self.config.timeout)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, params=params, headers=headers) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        raise PropertyDataError(
                            f"Provider returned status {resp.status}: {text[:200]}"
                        )
                    return await resp.json()
        except aiohttp.ClientError as e:
            raise PropertyDataError(f"Property data request failed: {e}") from e

    async def search(
        self,
        location: str,
        price_min: Optional[float] = None,
        price_max: Optional[float] = None,
        bedrooms_min: Optional[int] = None,
        bathrooms_min: Optional[float] = None,
        property_types: Optional[List[str]] = None,
        min_sqft: Optional[int] = None,
        max_results: int = 20,
        sort_by: str = "relevance",
    ) -> List[Property]:
        """
        Search for active property listings matching criteria.

        Args:
            location: City, ZIP code, neighborhood, or "lat,lng".
            price_min: Minimum list price.
            price_max: Maximum list price.
            bedrooms_min: Minimum number of bedrooms.
            bathrooms_min: Minimum number of bathrooms.
            property_types: Filter by property type(s).
            min_sqft: Minimum square footage.
            max_results: Maximum number of results to return.
            sort_by: Sort order (relevance, price_asc, price_desc, newest).

        Returns:
            List of matching Property records.
        """
        params: Dict[str, Any] = {
            "location": location,
            "limit": max_results,
            "sort": sort_by,
        }
        if price_min is not None:
            params["price_min"] = price_min
        if price_max is not None:
            params["price_max"] = price_max
        if bedrooms_min is not None:
            params["beds_min"] = bedrooms_min
        if bathrooms_min is not None:
            params["baths_min"] = bathrooms_min
        if property_types:
            params["property_type"] = ",".join(property_types)
        if min_sqft is not None:
            params["sqft_min"] = min_sqft

        try:
            data = await self._request("property/search", params)
            return [self._parse_property(item) for item in data.get("properties", [])]
        except PropertyDataError:
            logger.warning("Property search provider unavailable, returning empty results")
            return []

    async def get_details(self, property_id: str) -> Optional[Property]:
        """Get full details for a single property."""
        try:
            data = await self._request(f"property/{property_id}", {})
            item = data.get("property")
            return self._parse_property(item) if item else None
        except PropertyDataError:
            logger.warning(f"Failed to fetch details for property {property_id}")
            return None

    async def get_avm_estimate(self, property_id: str) -> Optional[ValuationEstimate]:
        """Get an automated valuation model (AVM) estimate for a property."""
        try:
            data = await self._request(f"property/{property_id}/avm", {})
            avm = data.get("avm")
            if not avm:
                return None
            return ValuationEstimate(
                property_id=property_id,
                estimated_value=avm["value"],
                value_range_low=avm.get("value_low", avm["value"] * 0.93),
                value_range_high=avm.get("value_high", avm["value"] * 1.07),
                confidence_score=avm.get("confidence", 0.7),
                last_updated=datetime.utcnow(),
                comparable_count=avm.get("comp_count", 0),
            )
        except PropertyDataError:
            logger.warning(f"Failed to fetch AVM estimate for property {property_id}")
            return None

    async def get_comparable_sales(
        self,
        property_id: str,
        radius_miles: float = 1.0,
        max_results: int = 5,
    ) -> List[ComparableSale]:
        """Get comparable recently-sold properties near the given property."""
        try:
            data = await self._request(
                f"property/{property_id}/comps",
                {"radius": radius_miles, "limit": max_results},
            )
            comps = []
            for item in data.get("comparables", []):
                comps.append(ComparableSale(
                    property_id=item["property_id"],
                    address=item["address"],
                    sale_price=item["sale_price"],
                    sale_date=datetime.fromisoformat(item["sale_date"]),
                    sqft=item.get("sqft"),
                    bedrooms=item.get("bedrooms"),
                    bathrooms=item.get("bathrooms"),
                    distance_miles=item.get("distance_miles", 0.0),
                ))
            return comps
        except PropertyDataError:
            logger.warning(f"Failed to fetch comparable sales for property {property_id}")
            return []

    def _parse_property(self, item: Dict[str, Any]) -> Property:
        """Parse a raw provider response into a Property object."""
        return Property(
            property_id=item.get("property_id", ""),
            address=item.get("address", ""),
            city=item.get("city", ""),
            state=item.get("state", ""),
            zip_code=item.get("zip_code", ""),
            latitude=item.get("latitude"),
            longitude=item.get("longitude"),
            list_price=item.get("list_price"),
            property_type=item.get("property_type", "single_family"),
            bedrooms=item.get("bedrooms"),
            bathrooms=item.get("bathrooms"),
            sqft=item.get("sqft"),
            lot_sqft=item.get("lot_sqft"),
            year_built=item.get("year_built"),
            status=item.get("status", "active"),
            days_on_market=item.get("days_on_market"),
            photos=item.get("photos", []),
            description=item.get("description"),
            features=item.get("features", []),
            hoa_fee=item.get("hoa_fee"),
            listing_agent=item.get("listing_agent"),
            price_history=item.get("price_history", []),
            tax_history=item.get("tax_history", []),
        )


def create_property_data_client(
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> PropertyDataClient:
    """Factory function to create a configured property data client."""
    config = PropertyDataConfig(
        provider=provider or "attom",
        base_url=base_url or "",
        api_key=api_key or "",
    )
    return PropertyDataClient(config)
