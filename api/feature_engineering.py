import re
import pandas as pd
from rapidfuzz import fuzz
import math

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    Returns distance in meters.
    """
    if None in [lat1, lon1, lat2, lon2]:
        return -1.0
        
    # convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])

    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a)) 
    r = 6371000 # Radius of earth in meters.
    return c * r

def build_feature_vector(row_a, row_b) -> dict:
    """
    Calculates features for a pair of restaurant records.
    """
    # Use normalized versions if available, otherwise raw
    name_a = row_a.get("_norm_name", row_a.get("name", ""))
    name_b = row_b.get("_norm_name", row_b.get("name", ""))
    
    base_a = row_a.get("_base_name", name_a)
    base_b = row_b.get("_base_name", name_b)
    
    addr_a = row_a.get("_norm_address", row_a.get("address", ""))
    addr_b = row_b.get("_norm_address", row_b.get("address", ""))
    
    phone_a = row_a.get("_norm_phone", row_a.get("phone", ""))
    phone_b = row_b.get("_norm_phone", row_b.get("phone", ""))
    
    muni_a = row_a.get("_municipality", "")
    muni_b = row_b.get("_municipality", "")
    
    features = {}
    
    # 1. Phone features
    features["phone_exact"] = 1.0 if phone_a and phone_b and phone_a == phone_b else 0.0
    features["phone_prefix_match"] = 1.0 if phone_a[:4] == phone_b[:4] and len(phone_a) > 4 else 0.0
    
    # 2. Name features
    features["name_ratio"] = fuzz.token_sort_ratio(name_a, name_b) / 100.0
    features["name_partial"] = fuzz.partial_ratio(name_a, name_b) / 100.0
    features["name_base_ratio"] = fuzz.token_sort_ratio(base_a, base_b) / 100.0
    features["name_len_diff"] = abs(len(name_a) - len(name_b))
    
    # 3. Address features
    features["addr_ratio"] = fuzz.token_sort_ratio(addr_a, addr_b) / 100.0
    features["addr_partial"] = fuzz.partial_ratio(addr_a, addr_b) / 100.0
    
    # 4. Location features
    features["same_municipality"] = 1.0 if muni_a and muni_b and muni_a == muni_b else 0.0
    
    # Distance (Exact Haversine)
    lat_a, lng_a = row_a.get("lat"), row_a.get("lng")
    lat_b, lng_b = row_b.get("lat"), row_b.get("lng")
    
    # Fallback to normalized lat/lng if not in raw
    if lat_a is None: lat_a = row_a.get("_lat")
    if lng_a is None: lng_a = row_a.get("_lng")
    if lat_b is None: lat_b = row_b.get("_lat")
    if lng_b is None: lng_b = row_b.get("_lng")
    
    dist_m = haversine_distance(lat_a, lng_a, lat_b, lng_b)
    features["geo_distance_meters"] = dist_m
        
    # 5. Branch keywords
    branch_regex = re.compile(r"(店|支店|号店|本店|ビル)")
    features["has_branch_keyword"] = 1.0 if branch_regex.search(name_a) or branch_regex.search(name_b) else 0.0
    
    return features
