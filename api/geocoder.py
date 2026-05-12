import os
import json
import httpx
import logging
import time
from typing import Tuple, Optional

logger = logging.getLogger("geocoder")

class GSIGeocoder:
    def __init__(self, cache_path: str = None):
        if cache_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            cache_path = os.path.join(base_dir, "data", "geocoding_cache.json")
            
        self.cache_path = cache_path
        self.cache = self._load_cache()
        self.api_url = "https://msearch.gsi.go.jp/address-search/AddressSearch"

    def _load_cache(self) -> dict:
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading geocoding cache: {e}")
        return {}

    def _save_cache(self):
        try:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving geocoding cache: {e}")

    def get_coordinates(self, address: str) -> Tuple[Optional[float], Optional[float]]:
        """
        Returns (latitude, longitude) for a given address.
        Uses local cache if available, otherwise calls GSI API.
        """
        if not address or not isinstance(address, str):
            return None, None
            
        # Clean address for cache key
        address_key = address.strip()
        if address_key in self.cache:
            res = self.cache[address_key]
            return res.get("lat"), res.get("lng")

        # Call GSI API
        try:
            params = {"q": address_key}
            # Shorter timeout to prevent server freeze
            response = httpx.get(self.api_url, params=params, timeout=2.0)
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    lng, lat = data[0]["geometry"]["coordinates"]
                    self.cache[address_key] = {"lat": lat, "lng": lng}
                    self._save_cache()
                    return lat, lng
        except (httpx.TimeoutException, httpx.NetworkError):
            logger.warning(f"Geocoding timeout/network error for {address}")
        except Exception as e:
            logger.error(f"Geocoding error for {address}: {e}")
            
        return None, None
