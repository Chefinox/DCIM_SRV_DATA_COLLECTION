# Compatibility Layer for DCIM Common
# This file bridges the old import style to the new modular architecture under src/

import sys
import os

# Original functionalities migrated to:
from src.configs.loader import read_secret
from src.configs.database import get_db_config
from src.schemas.transformers.asset_metadata import extract_metadata

# Backwards compatibility for DB_CONFIG as a dictionary
DB_CONFIG = get_db_config()

# Export all symbols for legacy scripts
__all__ = ['read_secret', 'get_db_config', 'DB_CONFIG', 'extract_metadata']
