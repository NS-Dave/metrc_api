"""
Cultivation-specific API operations for Metrc.
Handles plants, plant batches, harvests, and strains.
"""
from typing import Dict, List, Optional, Union
from datetime import datetime

from client import MetrcClient
from config import Endpoints


class CultivationClient:
    """Client for Cultivation license operations."""
    
    def __init__(self, client: MetrcClient):
        """
        Initialize cultivation client.
        
        Args:
            client: Configured MetrcClient instance
        """
        self.client = client
    
    # ==================== STRAINS ====================
    
    def get_strains(self, license_number: Optional[str] = None) -> List[Dict]:
        """
        Get all active strains.
        
        Args:
            license_number: License number (uses config default if not provided)
            
        Returns:
            List of strain objects
        """
        return self.client.get(Endpoints.STRAINS_ACTIVE, license_number=license_number)
    
    def create_strains(self, strains: List[Dict], license_number: Optional[str] = None):
        """
        Create new strains.
        
        Args:
            strains: List of strain objects with Name, TestingStatus, ThcLevel, etc.
            license_number: License number
            
        Example strain object:
            {
                "Name": "Spring Hill Kush",
                "TestingStatus": "None",
                "ThcLevel": 0.1865,
                "CbdLevel": 0.1075,
                "IndicaPercentage": 25.0,
                "SativaPercentage": 75.0
            }
        """
        return self.client.post(Endpoints.STRAINS_CREATE, data=strains, 
                               license_number=license_number)
    
    def update_strains(self, strains: List[Dict], license_number: Optional[str] = None):
        """Update existing strains."""
        return self.client.post(Endpoints.STRAINS_UPDATE, data=strains,
                               license_number=license_number)
    
    def delete_strain(self, strain_id: int, license_number: Optional[str] = None):
        """Delete a strain by ID."""
        endpoint = f"{Endpoints.STRAINS_DELETE}/{strain_id}"
        return self.client.delete(endpoint, data={}, license_number=license_number)
    
    # ==================== PLANT BATCHES ====================
    
    def get_plant_batches(
        self,
        status: str = 'active',
        last_modified_start: Optional[Union[datetime, str]] = None,
        last_modified_end: Optional[Union[datetime, str]] = None,
        license_number: Optional[str] = None
    ) -> List[Dict]:
        """
        Get plant batches.
        
        Args:
            status: 'active' or 'inactive'
            last_modified_start: Filter by last modified date
            last_modified_end: End of date range
            license_number: License number
            
        Returns:
            List of plant batch objects
        """
        endpoint = (Endpoints.PLANT_BATCHES_ACTIVE if status == 'active' 
                   else Endpoints.PLANT_BATCHES_INACTIVE)
        
        if last_modified_start:
            return self.client.get_with_last_modified(
                endpoint, last_modified_start, last_modified_end, license_number
            )
        
        return self.client.get(endpoint, license_number=license_number)
    
    def get_plant_batch_types(self, license_number: Optional[str] = None) -> List[str]:
        """Get available plant batch types."""
        return self.client.get(Endpoints.PLANT_BATCHES_TYPES, license_number=license_number)
    
    def create_plant_batches_from_packages(
        self,
        batches: List[Dict],
        license_number: Optional[str] = None
    ):
        """
        Create plant batches from packages (seeds/clones).
        
        Args:
            batches: List of plant batch creation objects
            license_number: License number
            
        Example batch object:
            {
                "Name": "B. Kush 5-30",
                "Type": "Seed",
                "Count": 25,
                "Strain": "Spring Hill Kush",
                "Location": "Germination A",
                "Item": "Blue Dream Seeds",
                "PatientLicenseNumber": null,
                "ActualDate": "2015-12-15"
            }
        """
        return self.client.post(Endpoints.PLANT_BATCHES_CREATE, data=batches,
                               license_number=license_number)
    
    def create_plant_batches_from_mother(
        self,
        plantings: List[Dict],
        license_number: Optional[str] = None
    ):
        """
        Create plantings (immature plants from mother plant).
        
        Args:
            plantings: List of planting objects
            license_number: License number
            
        Example planting object:
            {
                "PlantBatch": "B. Kush 5-30",
                "Count": 25,
                "Location": "Germination Room A",
                "Strain": "Spring Hill Kush",
                "PatientLicenseNumber": null,
                "ActualDate": "2015-12-15"
            }
        """
        return self.client.post(Endpoints.PLANT_BATCHES_CREATE, data=plantings,
                               license_number=license_number)
    
    def change_plant_batch_growth_phase(
        self,
        changes: List[Dict],
        license_number: Optional[str] = None
    ):
        """
        Change growth phase of plant batches (e.g., to Vegetative).
        
        Args:
            changes: List of growth phase change objects
            license_number: License number
            
        Example change object:
            {
                "Name": "B. Kush 5-30",
                "Count": 25,
                "StartingTag": "1A4FF01000000220000000010",
                "GrowthPhase": "Vegetative",
                "NewLocation": "Vegetation Room A",
                "GrowthDate": "2015-12-16",
                "PatientLicenseNumber": null
            }
        """
        return self.client.post(Endpoints.PLANT_BATCHES_CHANGE_GROWTH, data=changes,
                               license_number=license_number)
    
    def move_plant_batches(self, moves: List[Dict], license_number: Optional[str] = None):
        """
        Move plant batches to different locations.
        
        Args:
            moves: List of move objects with Name, Location, MoveDate
            license_number: License number
        """
        return self.client.put(Endpoints.PLANT_BATCHES_MOVE, data=moves,
                              license_number=license_number)
    
    def split_plant_batch(self, splits: List[Dict], license_number: Optional[str] = None):
        """
        Split plant batch into multiple batches.
        
        Args:
            splits: List of split objects
            license_number: License number
        """
        return self.client.post(Endpoints.PLANT_BATCHES_SPLIT, data=splits,
                               license_number=license_number)
    
    def add_plant_batch_additives(
        self,
        additives: List[Dict],
        license_number: Optional[str] = None
    ):
        """
        Record additives applied to plant batches.
        
        Args:
            additives: List of additive application objects
            license_number: License number
        """
        return self.client.post(Endpoints.PLANT_BATCHES_ADDITIVES, data=additives,
                               license_number=license_number)
    
    def destroy_plant_batches(
        self,
        destructions: List[Dict],
        license_number: Optional[str] = None
    ):
        """
        Destroy plant batches.
        
        Args:
            destructions: List of destruction objects
            license_number: License number
            
        Example destruction object:
            {
                "PlantBatch": "B. Kush 5-30",
                "Count": 20,
                "ReasonNote": "Contamination",
                "ActualDate": "2015-12-15"
            }
        """
        return self.client.post(Endpoints.PLANT_BATCHES_DESTROY, data=destructions,
                               license_number=license_number)
    
    # ==================== PLANTS ====================
    
    def get_plants(
        self,
        phase: str = 'vegetative',
        last_modified_start: Optional[Union[datetime, str]] = None,
        last_modified_end: Optional[Union[datetime, str]] = None,
        license_number: Optional[str] = None
    ) -> List[Dict]:
        """
        Get plants by growth phase.
        
        Args:
            phase: 'vegetative', 'flowering', 'onhold', or 'inactive'
            last_modified_start: Filter by last modified date
            last_modified_end: End of date range
            license_number: License number
            
        Returns:
            List of plant objects
        """
        endpoint_map = {
            'vegetative': Endpoints.PLANTS_VEGETATIVE,
            'flowering': Endpoints.PLANTS_FLOWERING,
            'onhold': Endpoints.PLANTS_ONHOLD,
            'inactive': Endpoints.PLANTS_INACTIVE
        }
        
        endpoint = endpoint_map.get(phase.lower(), Endpoints.PLANTS_VEGETATIVE)
        
        if last_modified_start:
            return self.client.get_with_last_modified(
                endpoint, last_modified_start, last_modified_end, license_number
            )
        
        return self.client.get(endpoint, license_number=license_number)
    
    def get_plant_growth_phases(self, license_number: Optional[str] = None) -> List[str]:
        """Get available plant growth phases."""
        return self.client.get(Endpoints.PLANTS_GROWTH_PHASES, license_number=license_number)
    
    def get_plant_waste_methods(self, license_number: Optional[str] = None) -> List[Dict]:
        """Get available waste methods for plants."""
        return self.client.get(Endpoints.PLANTS_WASTE_METHODS, license_number=license_number)
    
    def get_plant_waste_reasons(self, license_number: Optional[str] = None) -> List[Dict]:
        """Get available waste reasons for plants."""
        return self.client.get(Endpoints.PLANTS_WASTE_REASONS, license_number=license_number)
    
    def get_plant_additive_types(self, license_number: Optional[str] = None) -> List[str]:
        """Get available plant additive types."""
        return self.client.get(Endpoints.PLANTS_ADDITIVES_TYPES, license_number=license_number)
    
    def move_plants(self, moves: List[Dict], license_number: Optional[str] = None):
        """
        Move plants to different locations.
        
        Args:
            moves: List of move objects
            license_number: License number
            
        Example move object:
            {
                "Id": null,
                "Label": "1A4FF01000000220000000010",
                "Location": "Vegetation Room A",
                "ActualDate": "2015-12-15"
            }
        """
        return self.client.post(Endpoints.PLANTS_MOVE, data=moves,
                               license_number=license_number)
    
    def change_plant_growth_phase(
        self,
        changes: List[Dict],
        license_number: Optional[str] = None
    ):
        """
        Change growth phase of plants (e.g., Vegetative to Flowering).
        
        Args:
            changes: List of growth phase change objects
            license_number: License number
            
        Example change object:
            {
                "Id": null,
                "Label": "1A4FF01000000220000000010",
                "NewLabel": "1A4FF01000000220000000011",
                "GrowthPhase": "Flowering",
                "NewLocation": "Flowering Room A",
                "GrowthDate": "2015-12-16"
            }
        """
        return self.client.post(Endpoints.PLANTS_CHANGE_GROWTH, data=changes,
                               license_number=license_number)
    
    def destroy_plants(self, destructions: List[Dict], license_number: Optional[str] = None):
        """
        Destroy plants.
        
        Args:
            destructions: List of destruction objects with plant IDs/labels and reasons
            license_number: License number
        """
        return self.client.post(Endpoints.PLANTS_DESTROY, data=destructions,
                               license_number=license_number)
    
    def add_plant_additives(self, additives: List[Dict], license_number: Optional[str] = None):
        """
        Record additives applied to plants.
        
        Args:
            additives: List of additive application objects
            license_number: License number
        """
        return self.client.post(Endpoints.PLANTS_ADDITIVES, data=additives,
                               license_number=license_number)
    
    def manicure_plants(self, manicures: List[Dict], license_number: Optional[str] = None):
        """
        Record plant manicuring (trimming/pruning).
        
        Args:
            manicures: List of manicure objects
            license_number: License number
        """
        return self.client.post(Endpoints.PLANTS_MANICURE, data=manicures,
                               license_number=license_number)
    
    def harvest_plants(self, harvests: List[Dict], license_number: Optional[str] = None):
        """
        Harvest plants.
        
        Args:
            harvests: List of harvest objects
            license_number: License number
            
        Example harvest object:
            {
                "Plant": "1A4FF01000000220000000010",
                "Weight": 100.23,
                "UnitOfWeight": "Grams",
                "DryingLocation": "Drying Room A",
                "HarvestName": "2015-12-Harvest",
                "PatientLicenseNumber": null,
                "ActualDate": "2015-12-15"
            }
        """
        return self.client.post(Endpoints.PLANTS_HARVEST, data=harvests,
                               license_number=license_number)
    
    # ==================== HARVESTS ====================
    
    def get_harvests(
        self,
        status: str = 'active',
        last_modified_start: Optional[Union[datetime, str]] = None,
        last_modified_end: Optional[Union[datetime, str]] = None,
        license_number: Optional[str] = None
    ) -> List[Dict]:
        """
        Get harvests.
        
        Args:
            status: 'active', 'onhold', or 'inactive'
            last_modified_start: Filter by last modified date
            last_modified_end: End of date range
            license_number: License number
            
        Returns:
            List of harvest objects
        """
        endpoint_map = {
            'active': Endpoints.HARVESTS_ACTIVE,
            'onhold': Endpoints.HARVESTS_ONHOLD,
            'inactive': Endpoints.HARVESTS_INACTIVE
        }
        
        endpoint = endpoint_map.get(status.lower(), Endpoints.HARVESTS_ACTIVE)
        
        if last_modified_start:
            return self.client.get_with_last_modified(
                endpoint, last_modified_start, last_modified_end, license_number
            )
        
        return self.client.get(endpoint, license_number=license_number)
    
    def get_harvest_waste_types(self, license_number: Optional[str] = None) -> List[str]:
        """Get available harvest waste types."""
        return self.client.get(Endpoints.HARVESTS_WASTE_TYPES, license_number=license_number)
    
    def create_harvest_packages(
        self,
        packages: List[Dict],
        license_number: Optional[str] = None
    ):
        """
        Create packages from harvested material.
        
        Args:
            packages: List of package creation objects
            license_number: License number
            
        Example package object:
            {
                "Tag": "1A4FF01000000220000000100",
                "Location": null,
                "Item": "Buds",
                "UnitOfWeight": "Ounces",
                "PatientLicenseNumber": null,
                "Note": null,
                "IsProductionBatch": false,
                "ProductionBatchNumber": null,
                "IsTradeSample": false,
                "IsTesting Sample": false,
                "ProductRequiresRemediation": false,
                "RemediateProduct": false,
                "RemediationMethodId": null,
                "RemediationDate": null,
                "RemediationSteps": null,
                "ActualDate": "2015-12-15",
                "Ingredients": [
                    {
                        "HarvestId": 1,
                        "HarvestName": null,
                        "Weight": 100.23,
                        "UnitOfWeight": "Ounces"
                    }
                ]
            }
        """
        return self.client.post(Endpoints.HARVESTS_CREATE, data=packages,
                               license_number=license_number)
    
    def move_harvests(self, moves: List[Dict], license_number: Optional[str] = None):
        """Move harvests to different locations."""
        return self.client.put(Endpoints.HARVESTS_MOVE, data=moves,
                              license_number=license_number)
    
    def remove_harvest_waste(self, waste: List[Dict], license_number: Optional[str] = None):
        """
        Remove waste from harvest.
        
        Args:
            waste: List of waste removal objects
            license_number: License number
        """
        return self.client.post(Endpoints.HARVESTS_REMOVE_WASTE, data=waste,
                               license_number=license_number)
    
    def rename_harvest(self, renames: List[Dict], license_number: Optional[str] = None):
        """Rename harvest batches."""
        return self.client.put(Endpoints.HARVESTS_RENAME, data=renames,
                              license_number=license_number)
    
    def finish_harvests(self, finishes: List[Dict], license_number: Optional[str] = None):
        """
        Mark harvests as finished.
        
        Args:
            finishes: List of finish objects with harvest IDs and dates
            license_number: License number
        """
        return self.client.post(Endpoints.HARVESTS_FINISH, data=finishes,
                               license_number=license_number)
    
    def unfinish_harvests(self, unfinishes: List[Dict], license_number: Optional[str] = None):
        """Reopen finished harvests."""
        return self.client.post(Endpoints.HARVESTS_UNFINISH, data=unfinishes,
                               license_number=license_number)
