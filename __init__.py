"""
Main entry point for Metrc API client.
Provides convenient imports for common use cases.
"""

# Configuration
from config import MetrcConfig, LicenseType, Endpoints

# Core client
from client import (
    MetrcClient,
    MetrcAPIError,
    MetrcAuthenticationError,
    MetrcRateLimitError,
    MetrcValidationError
)

# Specialized clients
from cultivation import CultivationClient
from processing import ProcessingClient

# Utilities
from utils import (
    DateUtils,
    ValidationUtils,
    DataTransformUtils,
    ErrorFormatter,
    RateLimiter
)

__version__ = "1.0.0"
__author__ = "Your Organization"

# Convenience function for quick setup
def create_client(
    software_key: str = None,
    user_key: str = None,
    license_number: str = None,
    use_env: bool = True
):
    """
    Create a configured Metrc client.
    
    Args:
        software_key: Software API key (or use env var)
        user_key: User API key (or use env var)
        license_number: Default license number
        use_env: Load config from environment variables
        
    Returns:
        Tuple of (MetrcClient, CultivationClient, ProcessingClient)
    """
    if use_env:
        config = MetrcConfig.from_env()
    else:
        if not software_key or not user_key:
            raise ValueError("Must provide API keys or set use_env=True")
        config = MetrcConfig(
            software_api_key=software_key,
            user_api_key=user_key,
            license_number=license_number
        )
    
    client = MetrcClient(config)
    cultivation = CultivationClient(client)
    processing = ProcessingClient(client)
    
    return client, cultivation, processing


__all__ = [
    # Config
    'MetrcConfig',
    'LicenseType',
    'Endpoints',
    
    # Clients
    'MetrcClient',
    'CultivationClient',
    'ProcessingClient',
    
    # Exceptions
    'MetrcAPIError',
    'MetrcAuthenticationError',
    'MetrcRateLimitError',
    'MetrcValidationError',
    
    # Utils
    'DateUtils',
    'ValidationUtils',
    'DataTransformUtils',
    'ErrorFormatter',
    'RateLimiter',
    
    # Convenience
    'create_client',
]
