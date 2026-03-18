"""
Processing-specific API operations for Metrc.
Handles packages, items, lab tests, and transfers.
"""
from typing import Dict, List, Optional, Union
from datetime import datetime

from client import MetrcClient
from config import Endpoints


class ProcessingClient:
    """Client for Processing license operations."""
    
    def __init__(self, client: MetrcClient):
        """
        Initialize processing client.
        
        Args:
            client: Configured MetrcClient instance
        """
        self.client = client
    
    # ==================== PACKAGES ====================
    
    def get_packages(
        self,
        status: str = 'active',
        last_modified_start: Optional[Union[datetime, str]] = None,
        last_modified_end: Optional[Union[datetime, str]] = None,
        license_number: Optional[str] = None
    ) -> List[Dict]:
        """
        Get packages.
        
        Args:
            status: 'active', 'onhold', 'inactive', 'intransit', or 'transferred'
            last_modified_start: Filter by last modified date
            last_modified_end: End of date range
            license_number: License number
            
        Returns:
            List of package objects
        """
        endpoint_map = {
            'active': Endpoints.PACKAGES_ACTIVE,
            'onhold': Endpoints.PACKAGES_ONHOLD,
            'inactive': Endpoints.PACKAGES_INACTIVE,
            'intransit': Endpoints.PACKAGES_INTRANSIT,
            'transferred': Endpoints.PACKAGES_TRANSFERRED
        }
        
        endpoint = endpoint_map.get(status.lower(), Endpoints.PACKAGES_ACTIVE)
        
        if last_modified_start:
            return self.client.get_with_last_modified(
                endpoint, last_modified_start, last_modified_end, license_number
            )
        
        return self.client.get(endpoint, license_number=license_number)
    
    def get_package_types(self, license_number: Optional[str] = None) -> List[str]:
        """Get available package types."""
        return self.client.get(Endpoints.PACKAGES_TYPES, license_number=license_number)
    
    def get_package_adjust_reasons(self, license_number: Optional[str] = None) -> List[Dict]:
        """Get available adjustment reasons for packages."""
        return self.client.get(Endpoints.PACKAGES_ADJUST_REASONS, license_number=license_number)
    
    def create_packages(self, packages: List[Dict], license_number: Optional[str] = None):
        """
        Create new packages.
        
        Args:
            packages: List of package creation objects
            license_number: License number
            
        Example package object:
            {
                "Tag": "1A4FF01000000220000000100",
                "Location": null,
                "Item": "Buds",
                "Quantity": 16.0,
                "UnitOfMeasure": "Ounces",
                "PatientLicenseNumber": null,
                "Note": "This is a note",
                "IsProductionBatch": false,
                "ProductionBatchNumber": null,
                "IsTradeSample": false,
                "IsTesting Sample": false,
                "ProductRequiresRemediation": false,
                "ActualDate": "2015-12-15",
                "Ingredients": [
                    {
                        "Package": "1A4FF01000000220000000010",
                        "Quantity": 8.0,
                        "UnitOfMeasure": "Ounces"
                    }
                ]
            }
        """
        return self.client.post(Endpoints.PACKAGES_CREATE, data=packages,
                               license_number=license_number)
    
    def create_testing_packages(
        self,
        packages: List[Dict],
        license_number: Optional[str] = None
    ):
        """
        Create packages for testing purposes.
        
        Args:
            packages: List of testing package objects
            license_number: License number
        """
        return self.client.post(Endpoints.PACKAGES_CREATE_TESTING, data=packages,
                               license_number=license_number)
    
    def create_planting_packages(
        self,
        packages: List[Dict],
        license_number: Optional[str] = None
    ):
        """
        Create packages from plants for planting (seeds, clones).
        
        Args:
            packages: List of planting package objects
            license_number: License number
        """
        return self.client.post(Endpoints.PACKAGES_CREATE_PLANTINGS, data=packages,
                               license_number=license_number)
    
    def change_package_item(
        self,
        changes: List[Dict],
        license_number: Optional[str] = None
    ):
        """
        Change the item associated with a package.
        
        Args:
            changes: List of item change objects
            license_number: License number
            
        Example change object:
            {
                "Label": "1A4FF01000000220000000100",
                "Item": "Buds",
                "ActualDate": "2015-12-15"
            }
        """
        return self.client.post(Endpoints.PACKAGES_CHANGE_ITEM, data=changes,
                               license_number=license_number)
    
    def change_package_note(
        self,
        changes: List[Dict],
        license_number: Optional[str] = None
    ):
        """
        Change the note on a package.
        
        Args:
            changes: List of note change objects with Label and Note
            license_number: License number
        """
        return self.client.put(Endpoints.PACKAGES_CHANGE_NOTE, data=changes,
                              license_number=license_number)
    
    def adjust_packages(self, adjustments: List[Dict], license_number: Optional[str] = None):
        """
        Adjust package quantities.
        
        Args:
            adjustments: List of adjustment objects
            license_number: License number
            
        Example adjustment object:
            {
                "Label": "1A4FF01000000220000000100",
                "Quantity": -2.0,
                "UnitOfMeasure": "Ounces",
                "AdjustmentReason": "Waste",
                "AdjustmentDate": "2015-12-15",
                "ReasonNote": "Drying loss"
            }
        """
        return self.client.post(Endpoints.PACKAGES_ADJUST, data=adjustments,
                               license_number=license_number)
    
    def finish_packages(self, finishes: List[Dict], license_number: Optional[str] = None):
        """
        Finish (close) packages.
        
        Args:
            finishes: List of finish objects with Labels and ActualDate
            license_number: License number
        """
        return self.client.post(Endpoints.PACKAGES_FINISH, data=finishes,
                               license_number=license_number)
    
    def unfinish_packages(self, unfinishes: List[Dict], license_number: Optional[str] = None):
        """
        Reopen finished packages.
        
        Args:
            unfinishes: List of unfinish objects with Labels
            license_number: License number
        """
        return self.client.post(Endpoints.PACKAGES_UNFINISH, data=unfinishes,
                               license_number=license_number)
    
    def remediate_packages(
        self,
        remediations: List[Dict],
        license_number: Optional[str] = None
    ):
        """
        Remediate packages (products that failed testing).
        
        Args:
            remediations: List of remediation objects
            license_number: License number
        """
        return self.client.post(Endpoints.PACKAGES_REMEDIATE, data=remediations,
                               license_number=license_number)
    
    # ==================== ITEMS ====================
    
    def get_items(
        self,
        license_number: Optional[str] = None
    ) -> List[Dict]:
        """
        Get all active items (products).
        
        Args:
            license_number: License number
            
        Returns:
            List of item objects
        """
        return self.client.get(Endpoints.ITEMS_ACTIVE, license_number=license_number)
    
    def get_item_categories(self, license_number: Optional[str] = None) -> List[Dict]:
        """Get available item categories."""
        return self.client.get(Endpoints.ITEMS_CATEGORIES, license_number=license_number)
    
    def get_item_brands(self, license_number: Optional[str] = None) -> List[Dict]:
        """Get available item brands."""
        return self.client.get(Endpoints.ITEMS_BRANDS, license_number=license_number)
    
    def create_items(self, items: List[Dict], license_number: Optional[str] = None):
        """
        Create new items (products).
        
        Args:
            items: List of item creation objects
            license_number: License number
            
        Example item object:
            {
                "ItemCategory": "Buds",
                "Name": "Blue Dream Flower",
                "UnitOfMeasure": "Ounces",
                "Strain": "Blue Dream",
                "UnitCbdPercent": null,
                "UnitCbdContent": null,
                "UnitCbdContentUnitOfMeasure": null,
                "UnitThcPercent": null,
                "UnitThcContent": null,
                "UnitThcContentUnitOfMeasure": null,
                "UnitVolume": null,
                "UnitVolumeUnitOfMeasure": null,
                "UnitWeight": null,
                "UnitWeightUnitOfMeasure": null,
                "ServingSize": null,
                "SupplyDurationDays": null,
                "Ingredients": null,
                "Description": null
            }
        """
        return self.client.post(Endpoints.ITEMS_CREATE, data=items,
                               license_number=license_number)
    
    def update_items(self, items: List[Dict], license_number: Optional[str] = None):
        """
        Update existing items.
        
        Args:
            items: List of item update objects (must include Id)
            license_number: License number
        """
        return self.client.post(Endpoints.ITEMS_UPDATE, data=items,
                               license_number=license_number)
    
    def delete_item(self, item_id: int, license_number: Optional[str] = None):
        """
        Delete an item by ID.
        
        Args:
            item_id: Item ID
            license_number: License number
        """
        endpoint = f"{Endpoints.ITEMS_DELETE}/{item_id}"
        return self.client.delete(endpoint, data={}, license_number=license_number)
    
    # ==================== LAB TESTS ====================
    
    def get_lab_test_states(self, license_number: Optional[str] = None) -> List[str]:
        """Get available lab test states."""
        return self.client.get(Endpoints.LAB_TESTS_STATES, license_number=license_number)
    
    def get_lab_test_types(self, license_number: Optional[str] = None) -> List[Dict]:
        """Get available lab test types."""
        return self.client.get(Endpoints.LAB_TESTS_TYPES, license_number=license_number)
    
    def get_lab_test_results(
        self,
        package_id: int,
        license_number: Optional[str] = None
    ) -> List[Dict]:
        """
        Get lab test results for a package.
        
        Args:
            package_id: Package ID
            license_number: License number
            
        Returns:
            List of lab test result objects
        """
        endpoint = f"{Endpoints.LAB_TESTS_RESULTS}/{package_id}"
        return self.client.get(endpoint, license_number=license_number)
    
    def record_lab_test_results(
        self,
        results: List[Dict],
        license_number: Optional[str] = None
    ):
        """
        Record lab test results.
        
        Args:
            results: List of lab test result objects
            license_number: License number
            
        Example result object:
            {
                "Label": "1A4FF01000000220000000100",
                "ResultDate": "2015-12-15",
                "LabTestDocument": {
                    "DocumentFileName": "test-results.pdf",
                    "DocumentFileBase64": "base64encodedstring"
                },
                "Results": [
                    {
                        "LabTestTypeName": "THC",
                        "Quantity": 23.5,
                        "Passed": true,
                        "Notes": ""
                    }
                ]
            }
        """
        return self.client.post(Endpoints.LAB_TESTS_RECORD, data=results,
                               license_number=license_number)
    
    # ==================== TRANSFERS ====================
    
    def get_incoming_transfers(
        self,
        last_modified_start: Optional[Union[datetime, str]] = None,
        last_modified_end: Optional[Union[datetime, str]] = None,
        license_number: Optional[str] = None
    ) -> List[Dict]:
        """
        Get incoming transfers.
        
        Args:
            last_modified_start: Filter by last modified date
            last_modified_end: End of date range
            license_number: License number
            
        Returns:
            List of incoming transfer objects
        """
        if last_modified_start:
            return self.client.get_with_last_modified(
                Endpoints.TRANSFERS_INCOMING,
                last_modified_start,
                last_modified_end,
                license_number
            )
        
        return self.client.get(Endpoints.TRANSFERS_INCOMING, license_number=license_number)
    
    def get_outgoing_transfers(
        self,
        last_modified_start: Optional[Union[datetime, str]] = None,
        last_modified_end: Optional[Union[datetime, str]] = None,
        license_number: Optional[str] = None
    ) -> List[Dict]:
        """
        Get outgoing transfers.
        
        Args:
            last_modified_start: Filter by last modified date
            last_modified_end: End of date range
            license_number: License number
            
        Returns:
            List of outgoing transfer objects
        """
        if last_modified_start:
            return self.client.get_with_last_modified(
                Endpoints.TRANSFERS_OUTGOING,
                last_modified_start,
                last_modified_end,
                license_number
            )
        
        return self.client.get(Endpoints.TRANSFERS_OUTGOING, license_number=license_number)
    
    def get_rejected_transfers(
        self,
        license_number: Optional[str] = None
    ) -> List[Dict]:
        """Get rejected transfers."""
        return self.client.get(Endpoints.TRANSFERS_REJECTED, license_number=license_number)
    
    def get_transfer_types(self, license_number: Optional[str] = None) -> List[str]:
        """Get available transfer types."""
        return self.client.get(Endpoints.TRANSFERS_TYPES, license_number=license_number)
    
    def get_transfer_delivery(
        self,
        delivery_id: int,
        license_number: Optional[str] = None
    ) -> Dict:
        """
        Get delivery details (packages/wholesale) for a specific delivery.
        
        Args:
            delivery_id: Delivery ID (from transfer deliveries array)
            license_number: License number
            
        Returns:
            Delivery packages object
        """
        endpoint = f"{Endpoints.TRANSFERS_DELIVERY}/{delivery_id}/packages/wholesale"
        return self.client.get(endpoint, license_number=license_number)
    
    # ==================== LOCATIONS ====================
    
    def get_locations(self, license_number: Optional[str] = None) -> List[Dict]:
        """
        Get all active locations.
        
        Args:
            license_number: License number
            
        Returns:
            List of location objects
        """
        return self.client.get(Endpoints.LOCATIONS_ACTIVE, license_number=license_number)
    
    def get_location_types(self, license_number: Optional[str] = None) -> List[Dict]:
        """Get available location types."""
        return self.client.get(Endpoints.LOCATIONS_TYPES, license_number=license_number)
    
    def create_locations(self, locations: List[Dict], license_number: Optional[str] = None):
        """
        Create new locations.
        
        Args:
            locations: List of location objects
            license_number: License number
            
        Example location object:
            {
                "Name": "Harvest Location A",
                "LocationTypeName": "Default"
            }
        """
        return self.client.post(Endpoints.LOCATIONS_CREATE, data=locations,
                               license_number=license_number)
    
    def update_locations(self, locations: List[Dict], license_number: Optional[str] = None):
        """
        Update existing locations.
        
        Args:
            locations: List of location update objects (must include Id)
            license_number: License number
        """
        return self.client.post(Endpoints.LOCATIONS_UPDATE, data=locations,
                               license_number=license_number)
    
    def delete_location(self, location_id: int, license_number: Optional[str] = None):
        """
        Delete a location by ID.
        
        Args:
            location_id: Location ID
            license_number: License number
        """
        endpoint = f"{Endpoints.LOCATIONS_DELETE}/{location_id}"
        return self.client.delete(endpoint, data={}, license_number=license_number)
    
    # ==================== UNITS OF MEASURE ====================
    
    def get_units_of_measure(self, license_number: Optional[str] = None) -> List[Dict]:
        """
        Get all active units of measure.
        
        Args:
            license_number: License number
            
        Returns:
            List of unit of measure objects
        """
        return self.client.get(Endpoints.UOM_ACTIVE, license_number=license_number)
