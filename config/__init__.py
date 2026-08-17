"""
Config package - Contains configuration and registry.
"""

from config.settings import Settings, settings
from config.registry import ModelRegistry, registry, register_models

__all__ = [
    'Settings',
    'settings',
    'ModelRegistry',
    'registry',
    'register_models'
]
