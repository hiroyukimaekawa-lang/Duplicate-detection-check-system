import re
import pandas as pd
from typing import List, Optional

def mask_phone(phone: str) -> str:
    """
    Masks the middle digits of a phone number.
    Example: 09012345678 -> 090****5678
    """
    if not phone or not isinstance(phone, str):
        return phone
        
    # Remove non-digits for logic, but keep original if it doesn't match
    digits = re.sub(r'\D', '', phone)
    
    if len(digits) >= 10:
        # Standard Japanese phone (10 or 11 digits)
        # Mask 4th to 7th/8th digits
        prefix = phone[:3]
        suffix = phone[-4:]
        masked_len = len(phone) - len(prefix) - len(suffix)
        return prefix + ("*" * masked_len) + suffix
        
    return phone

def mask_email(email: str) -> str:
    """
    Masks the local part of an email address.
    Example: test@example.com -> t***@example.com
    """
    if not email or "@" not in email:
        return email
        
    local, domain = email.split("@", 1)
    if len(local) > 1:
        return local[0] + "***" + "@" + domain
    return "*" + "@" + domain

def apply_privacy_masking(df: pd.DataFrame, columns: List[str] = None) -> pd.DataFrame:
    """
    Applies masking to specified columns in a DataFrame.
    Default columns: ['phone', 'email', 'representative', 'owner']
    """
    if df.empty:
        return df
        
    target_cols = columns or ['phone', 'email', 'representative', 'owner']
    masked_df = df.copy()
    
    for col in target_cols:
        if col in masked_df.columns:
            if col == 'phone':
                masked_df[col] = masked_df[col].apply(mask_phone)
            elif col == 'email':
                masked_df[col] = masked_df[col].apply(mask_email)
            else:
                # General name masking (Last name + **)
                def mask_name(name):
                    if not name or not isinstance(name, str): return name
                    return name[0] + "**"
                masked_df[col] = masked_df[col].apply(mask_name)
                
    return masked_df
