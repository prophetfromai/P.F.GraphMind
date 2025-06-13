# This file makes the app directory a Python package 

from .main import app
from .core.database import neo4j_connection
from .config import settings
__version__ = "0.1.0"  # You can update this as needed

__all__ = [
    'app',
    'settings',
    'neo4j_connection',
    'settings',
    '__version__'
] 