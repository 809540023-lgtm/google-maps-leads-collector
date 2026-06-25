from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class GeocodeResult:
    latitude: float
    longitude: float
    source: str
    formatted_address: str = ""


KNOWN_ADDRESS_COORDINATES: dict[str, GeocodeResult] = {
    "新北市泰山區楓江路40-2號": GeocodeResult(
        latitude=25.062426,
        longitude=121.43474,
        source="local_override",
        formatted_address="新北市泰山區楓江路40-2號",
    ),
    "新北市泰山區楓江路40之2號": GeocodeResult(
        latitude=25.062426,
        longitude=121.43474,
        source="local_override",
        formatted_address="新北市泰山區楓江路40之2號",
    ),
}

COORD_PAIR_PATTERN = re.compile(
    r"(?P<lat>[+-]?\d{1,3}(?:\.\d+)?)\s*[,，]\s*(?P<lng>[+-]?\d{1,3}(?:\.\d+)?)"
)
GOOGLE_MAPS_AT_PATTERN = re.compile(
    r"@(?P<lat>[+-]?\d{1,3}(?:\.\d+)?),(?P<lng>[+-]?\d{1,3}(?:\.\d+)?)(?:,|z|/|$)"
)
GOOGLE_MAPS_DATA_PATTERN = re.compile(
    r"!3d(?P<lat>[+-]?\d{1,3}(?:\.\d+)?)!4d(?P<lng>[+-]?\d{1,3}(?:\.\d+)?)"
)


def _normalize_address_key(address: str) -> str:
    return (
        address.strip()
        .replace(" ", "")
        .replace("台", "臺")
        .replace("-", "之")
    )


def _coordinate_result(latitude: float, longitude: float, source: str, original: str) -> GeocodeResult | None:
    if -90 <= latitude <= 90 and -180 <= longitude <= 180:
        return GeocodeResult(
            latitude=round(latitude, 6),
            longitude=round(longitude, 6),
            source=source,
            formatted_address=f"{latitude:.6f},{longitude:.6f}",
        )
    if -90 <= longitude <= 90 and -180 <= latitude <= 180:
        return GeocodeResult(
            latitude=round(longitude, 6),
            longitude=round(latitude, 6),
            source=f"{source}_swapped",
            formatted_address=f"{longitude:.6f},{latitude:.6f}",
        )
    return None


def _result_from_match(match: re.Match[str], source: str, original: str) -> GeocodeResult | None:
    return _coordinate_result(float(match.group("lat")), float(match.group("lng")), source, original)


def parse_coordinates(value: str) -> GeocodeResult | None:
    text = unquote(value.strip())
    if not text:
        return None

    for pattern, source in (
        (GOOGLE_MAPS_DATA_PATTERN, "google_maps_url"),
        (GOOGLE_MAPS_AT_PATTERN, "google_maps_url"),
        (COORD_PAIR_PATTERN, "coordinates"),
    ):
        match = pattern.search(text)
        if match:
            result = _result_from_match(match, source, value)
            if result:
                return result

    parsed = urlparse(text)
    query_values = parse_qs(parsed.query)
    for key in ("q", "query", "ll", "sll", "center"):
        for item in query_values.get(key, []):
            match = COORD_PAIR_PATTERN.search(unquote(item))
            if match:
                result = _result_from_match(match, "url_query_coordinates", value)
                if result:
                    return result
    return None


def haversine_distance_m(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    radius_m = 6_371_000
    lat_a = math.radians(latitude_a)
    lat_b = math.radians(latitude_b)
    delta_lat = math.radians(latitude_b - latitude_a)
    delta_lon = math.radians(longitude_b - longitude_a)
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2) ** 2
    )
    return radius_m * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def bounding_box(latitude: float, longitude: float, radius_m: int) -> tuple[float, float, float, float]:
    lat_delta = radius_m / 111_320
    lon_delta = radius_m / (111_320 * max(math.cos(math.radians(latitude)), 0.01))
    return (
        round(latitude - lat_delta, 6),
        round(longitude - lon_delta, 6),
        round(latitude + lat_delta, 6),
        round(longitude + lon_delta, 6),
    )


def geocode_address(address: str) -> GeocodeResult | None:
    if not address.strip():
        return None
    coordinate_result = parse_coordinates(address)
    if coordinate_result:
        return coordinate_result
    normalized_address = _normalize_address_key(address)
    for known_address, result in KNOWN_ADDRESS_COORDINATES.items():
        if _normalize_address_key(known_address) == normalized_address:
            return result
    if os.getenv("GOOGLE_GEOCODING_API_KEY"):
        return _geocode_google(address, os.environ["GOOGLE_GEOCODING_API_KEY"])
    return _geocode_nominatim(address)


def _geocode_google(address: str, api_key: str) -> GeocodeResult | None:
    query = urlencode({"address": address, "key": api_key, "language": "zh-TW"})
    request = Request(f"https://maps.googleapis.com/maps/api/geocode/json?{query}")
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    results = payload.get("results") or []
    if not results:
        return None
    location = (((results[0] or {}).get("geometry") or {}).get("location") or {})
    if "lat" not in location or "lng" not in location:
        return None
    return GeocodeResult(
        latitude=float(location["lat"]),
        longitude=float(location["lng"]),
        source="google",
        formatted_address=str(results[0].get("formatted_address") or address),
    )


def _geocode_nominatim(address: str) -> GeocodeResult | None:
    query = urlencode({"format": "jsonv2", "limit": 1, "q": address})
    request = Request(
        f"https://nominatim.openstreetmap.org/search?{query}",
        headers={"User-Agent": "codex-google-maps-leads/1.0"},
    )
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    if not payload:
        return None
    result = payload[0]
    return GeocodeResult(
        latitude=float(result["lat"]),
        longitude=float(result["lon"]),
        source="nominatim",
        formatted_address=str(result.get("display_name") or address),
    )
