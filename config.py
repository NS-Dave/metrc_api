"""
Configuration management for Metrc API integration.
Handles API credentials, endpoints, and Massachusetts-specific settings.
"""
import os
from typing import Optional
from dataclasses import dataclass


@dataclass
class MetrcConfig:
    """Configuration for Metrc API client."""
    
    # API credentials
    software_api_key: str
    user_api_key: str
    
    # State and base URL (Massachusetts uses MA state code)
    state: str = "MA"
    base_url: str = "https://api-ma.metrc.com"
    
    # License information
    license_number: Optional[str] = None
    license_type: Optional[str] = None  # "Cultivation" or "Processing"
    
    # API settings
    api_version: str = "v2"
    timeout: int = 30
    max_retries: int = 3
    retry_delay: int = 1  # seconds
    
    # Rate limiting
    requests_per_second: float = 10.0  # Adjust based on Metrc limits
    
    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = "metrc_api.log"
    
    @classmethod
    def from_env(cls) -> 'MetrcConfig':
        """
        Create configuration from environment variables.
        
        Required environment variables:
        - METRC_SOFTWARE_API_KEY: Your integrator API key
        - METRC_USER_API_KEY: The user's API key
        
        Optional environment variables:
        - METRC_LICENSE_NUMBER: Facility license number
        - METRC_LICENSE_TYPE: "Cultivation" or "Processing"
        - METRC_STATE: State code (default: MA)
        - METRC_TIMEOUT: Request timeout in seconds (default: 30)
        - METRC_LOG_LEVEL: Logging level (default: INFO)
        """
        software_key = os.getenv("METRC_SOFTWARE_API_KEY")
        user_key = os.getenv("METRC_USER_API_KEY")
        
        if not software_key or not user_key:
            raise ValueError(
                "METRC_SOFTWARE_API_KEY and METRC_USER_API_KEY must be set in environment variables"
            )
        
        state = os.getenv("METRC_STATE", "MA")
        base_url = f"https://api-{state.lower()}.metrc.com"
        
        return cls(
            software_api_key=software_key,
            user_api_key=user_key,
            state=state,
            base_url=base_url,
            license_number=os.getenv("METRC_LICENSE_NUMBER"),
            license_type=os.getenv("METRC_LICENSE_TYPE"),
            timeout=int(os.getenv("METRC_TIMEOUT", "30")),
            log_level=os.getenv("METRC_LOG_LEVEL", "INFO"),
        )
    
    def get_endpoint_url(self, endpoint: str) -> str:
        """
        Construct full URL for an API endpoint.
        
        Args:
            endpoint: API endpoint path (e.g., 'facilities/v2' or 'plants/v2/vegetative')
            
        Returns:
            Full URL for the endpoint
        """
        # Remove leading slash if present
        endpoint = endpoint.lstrip('/')
        
        # Endpoints already include version (e.g., 'facilities/v2'), so just join with base URL
        return f"{self.base_url}/{endpoint}"


# License type constants
class LicenseType:
    """Valid license types for Massachusetts."""
    CULTIVATION = "Cultivation"
    PROCESSING = "Processing"
    RETAIL = "Retail"  # Not used in current setup
    TESTING = "Testing"
    TRANSPORTATION = "Transportation"


# API endpoint paths
class Endpoints:
    """Metrc API v2 endpoint paths."""
    
    # Facilities
    FACILITIES = "facilities/v2"
    
    # Strains
    STRAINS_ACTIVE = "strains/v2/active"
    STRAINS_CREATE = "strains/v2/create"
    STRAINS_UPDATE = "strains/v2/update"
    STRAINS_DELETE = "strains/v2"
    
    # Plant Batches
    PLANT_BATCHES_ACTIVE = "plantbatches/v2/active"
    PLANT_BATCHES_INACTIVE = "plantbatches/v2/inactive"
    PLANT_BATCHES_TYPES = "plantbatches/v2/types"
    PLANT_BATCHES_CREATE = "plantbatches/v2/createplantings"
    PLANT_BATCHES_CREATE_PACKAGES = "plantbatches/v2/create/packages"
    PLANT_BATCHES_CHANGE_GROWTH = "plantbatches/v2/changegrowthphase"
    PLANT_BATCHES_MOVE = "plantbatches/v2/move"
    PLANT_BATCHES_SPLIT = "plantbatches/v2/split"
    PLANT_BATCHES_ADDITIVES = "plantbatches/v2/additives"
    PLANT_BATCHES_DESTROY = "plantbatches/v2/destroy"
    
    # Plants
    PLANTS_VEGETATIVE = "plants/v2/vegetative"
    PLANTS_FLOWERING = "plants/v2/flowering"
    PLANTS_ONHOLD = "plants/v2/onhold"
    PLANTS_INACTIVE = "plants/v2/inactive"
    PLANTS_ADDITIVES = "plants/v2/additives"
    PLANTS_ADDITIVES_TYPES = "plants/v2/additives/types"
    PLANTS_GROWTH_PHASES = "plants/v2/growthphases"
    PLANTS_WASTE_METHODS = "plants/v2/waste/methods"
    PLANTS_WASTE_REASONS = "plants/v2/waste/reasons"
    PLANTS_MOVE = "plants/v2/moveplants"
    PLANTS_CHANGE_GROWTH = "plants/v2/changegrowthphases"
    PLANTS_DESTROY = "plants/v2/destroyplants"
    PLANTS_MANICURE = "plants/v2/manicureplants"
    PLANTS_HARVEST = "plants/v2/harvestplants"
    
    # Harvests
    HARVESTS_ACTIVE = "harvests/v2/active"
    HARVESTS_ONHOLD = "harvests/v2/onhold"
    HARVESTS_INACTIVE = "harvests/v2/inactive"
    HARVESTS_WASTE_TYPES = "harvests/v2/waste/types"
    HARVESTS_CREATE = "harvests/v2/create/packages"
    HARVESTS_MOVE = "harvests/v2/move"
    HARVESTS_REMOVE_WASTE = "harvests/v2/removewaste"
    HARVESTS_RENAME = "harvests/v2/rename"
    HARVESTS_FINISH = "harvests/v2/finish"
    HARVESTS_UNFINISH = "harvests/v2/unfinish"
    
    # Packages
    PACKAGES_ACTIVE = "packages/v2/active"
    PACKAGES_ONHOLD = "packages/v2/onhold"
    PACKAGES_INACTIVE = "packages/v2/inactive"
    PACKAGES_TYPES = "packages/v2/types"
    PACKAGES_ADJUST_REASONS = "packages/v2/adjust/reasons"
    PACKAGES_CREATE = "packages/v2/create"
    PACKAGES_CREATE_TESTING = "packages/v2/create/testing"
    PACKAGES_CREATE_PLANTINGS = "packages/v2/create/plantings"
    PACKAGES_CHANGE_ITEM = "packages/v2/change/item"
    PACKAGES_CHANGE_NOTE = "packages/v2/change/note"
    PACKAGES_ADJUST = "packages/v2/adjust"
    PACKAGES_FINISH = "packages/v2/finish"
    PACKAGES_UNFINISH = "packages/v2/unfinish"
    PACKAGES_REMEDIATE = "packages/v2/remediate"
    
    # Items
    ITEMS_ACTIVE = "items/v2/active"
    ITEMS_CATEGORIES = "items/v2/categories"
    ITEMS_BRANDS = "items/v2/brands"
    ITEMS_CREATE = "items/v2/create"
    ITEMS_UPDATE = "items/v2/update"
    ITEMS_DELETE = "items/v2"
    
    # Locations
    LOCATIONS_ACTIVE = "locations/v2/active"
    LOCATIONS_TYPES = "locations/v2/types"
    LOCATIONS_CREATE = "locations/v2/create"
    LOCATIONS_UPDATE = "locations/v2/update"
    LOCATIONS_DELETE = "locations/v2"
    
    # Lab Tests
    LAB_TESTS_STATES = "labtests/v2/states"
    LAB_TESTS_TYPES = "labtests/v2/types"
    LAB_TESTS_RESULTS = "labtests/v2/results"
    LAB_TESTS_RECORD = "labtests/v2/record"
    
    # Transfers (for processing/distribution)
    TRANSFERS_INCOMING = "transfers/v2/incoming"
    TRANSFERS_OUTGOING = "transfers/v2/outgoing"
    TRANSFERS_REJECTED = "transfers/v2/rejected"
    TRANSFERS_DELIVERY = "transfers/v2/deliveries"
    TRANSFERS_TYPES = "transfers/v2/types"
    
    # Employees
    EMPLOYEES = "employees/v2"
    
    # UOM (Units of Measure)
    UOM_ACTIVE = "unitsofmeasure/v2/active"
