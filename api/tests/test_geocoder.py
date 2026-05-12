import pytest
from ..geocoder import GSIGeocoder

def test_geocoder_real_address():
    geocoder = GSIGeocoder()
    # Shinjuku Station (Approx)
    addr = "東京都新宿区新宿3-38-1"
    lat, lng = geocoder.get_coordinates(addr)
    
    assert lat is not None
    assert lng is not None
    # Shinjuku is approx 35.69, 139.70
    assert 35.6 <= lat <= 35.8
    assert 139.6 <= lng <= 139.8

def test_geocoder_cache():
    geocoder = GSIGeocoder()
    addr = "東京都渋谷区道玄坂1-1-1"
    
    # First call (might hit API)
    lat1, lng1 = geocoder.get_coordinates(addr)
    
    # Second call (must hit cache)
    lat2, lng2 = geocoder.get_coordinates(addr)
    
    assert lat1 == lat2
    assert lng1 == lng2
    assert addr in geocoder.cache
