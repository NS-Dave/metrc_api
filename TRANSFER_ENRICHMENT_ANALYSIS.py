"""
Comprehensive analysis of Metrc V2 Transfer API endpoints
to identify enrichment opportunities.

Based on:
- OpenMetrc V2 endpoints
- Cannlytics transfer models
- Current implementation gaps
"""

# =============================================================================
# V2 TRANSFER ENDPOINTS AVAILABLE (from OpenMetrc research)
# =============================================================================

TRANSFER_ENDPOINTS_V2 = {
    # ----------------- BASE TRANSFER QUERIES -----------------
    'get_transfers_v2_incoming': {
        'endpoint': '/transfers/v2/incoming',
        'current': 'YES',
        'description': 'Get incoming transfers',
        'params': ['licenseNumber', 'lastModifiedStart', 'lastModifiedEnd', 'pageNumber', 'pageSize']
    },
    'get_transfers_v2_outgoing': {
        'endpoint': '/transfers/v2/outgoing',
        'current': 'YES',
        'description': 'Get outgoing transfers',
        'params': ['licenseNumber', 'lastModifiedStart', 'lastModifiedEnd', 'pageNumber', 'pageSize']
    },
    'get_transfers_v2_rejected': {
        'endpoint': '/transfers/v2/rejected',
        'current': 'YES',
        'description': 'Get rejected transfers',
        'params': ['licenseNumber', 'pageNumber', 'pageSize']
    },
    'get_transfers_v2_hub': {
        'endpoint': '/transfers/v2/hub',
        'current': 'NO - OPPORTUNITY',
        'description': 'Get hub transfers (distribution hub model)',
        'params': ['licenseNumber', 'lastModifiedStart', 'lastModifiedEnd', 'pageNumber', 'pageSize'],
        'value': 'Hub transfers for multi-stop distribution - may have additional routing data'
    },
    
    # ----------------- DELIVERY DETAIL ENDPOINTS -----------------
    'get_transfers_v2_id_deliveries': {
        'endpoint': '/transfers/v2/{id}/deliveries',
        'current': 'NO - POTENTIAL',
        'description': 'Get all deliveries for a transfer',
        'params': ['id'],
        'value': 'More complete delivery list than embedded Deliveries array'
    },
    'get_transfers_v2_deliveries_id_packages': {
        'endpoint': '/transfers/v2/deliveries/{id}/packages',
        'current': 'PARTIAL - using wholesale variant',
        'description': 'Get packages for a delivery (standard)',
        'params': ['id', 'pageNumber', 'pageSize'],
        'value': 'Standard package details without wholesale pricing'
    },
    'get_transfers_v2_deliveries_id_packages_wholesale': {
        'endpoint': '/transfers/v2/deliveries/{id}/packages/wholesale',
        'current': 'YES',
        'description': 'Get packages with wholesale pricing',
        'params': ['id', 'pageNumber', 'pageSize'],
        'value': 'Currently using this for enrichment'
    },
    
    # ----------------- TRANSPORTER DETAILS -----------------
    'get_transfers_v2_deliveries_id_transporters': {
        'endpoint': '/transfers/v2/deliveries/{id}/transporters',
        'current': 'NO - OPPORTUNITY',
        'description': 'Get transporter info for delivery',
        'params': ['id', 'pageNumber', 'pageSize'],
        'value': 'Driver, vehicle, route information not currently captured',
        'fields': [
            'TransporterFacilityLicenseNumber',
            'DriverOccupationalLicenseNumber',
            'DriverName',
            'DriverLicenseNumber',
            'PhoneNumberForQuestions',
            'VehicleMake',
            'VehicleModel',
            'VehicleLicensePlateNumber',
            'IsLayover',
            'EstimatedDepartureDateTime',
            'EstimatedArrivalDateTime',
            'ActualDepartureDateTime',
            'ActualArrivalDateTime'
        ]
    },
    'get_transfers_v2_deliveries_id_transporters_details': {
        'endpoint': '/transfers/v2/deliveries/{id}/transporters/details',
        'current': 'NO - OPPORTUNITY',
        'description': 'Detailed transporter data (driver/vehicle specifics)',
        'params': ['id', 'pageNumber', 'pageSize'],
        'value': 'Granular transporter details beyond basic info'
    },
    
    # ----------------- LAB TESTING -----------------
    'get_transfers_v2_deliveries_package_id_requiredlabtestbatches': {
        'endpoint': '/transfers/v2/deliveries/package/{id}/requiredlabtestbatches',
        'current': 'NO - OPPORTUNITY',
        'description': 'Get required lab test batches for a package in transfer',
        'params': ['id', 'pageNumber', 'pageSize'],
        'value': 'Testing requirements for transferred packages - compliance tracking'
    },
    
    # ----------------- METADATA -----------------
    'get_transfers_v2_deliveries_packages_states': {
        'endpoint': '/transfers/v2/deliveries/packages/states',
        'current': 'NO - LOW PRIORITY',
        'description': 'Get all valid package states for transfers',
        'params': [],
        'value': 'Reference data - low priority'
    },
    'get_transfers_v2_types': {
        'endpoint': '/transfers/v2/types',
        'current': 'YES',
        'description': 'Get all transfer types',
        'params': ['licenseNumber', 'pageNumber', 'pageSize'],
        'value': 'Already using for reference'
    },
    
    # ----------------- TEMPLATES (outgoing only) -----------------
    'get_transfers_v2_templates_outgoing': {
        'endpoint': '/transfers/v2/templates/outgoing',
        'current': 'NO - NOT APPLICABLE',
        'description': 'Get transfer templates',
        'params': ['licenseNumber', 'pageNumber', 'pageSize'],
        'value': 'Templates for creating transfers - not relevant for incoming data'
    },
}

# =============================================================================
# CURRENT EXTRACTION vs AVAILABLE FIELDS
# =============================================================================

CURRENT_FIELDS = [
    'id',
    'manifest_number',
    'license_number',
    'shipper_facility_name',
    'shipper_facility_license_number',
    'transporter_facility_name',
    'transporter_facility_license_number',
    'destination_facility_name',
    'destination_facility_license_number',
    'created_date',
    'transfer_type',
    'shipment_type',
    'est_departure_datetime',
    'est_arrival_datetime',
    'actual_departure_datetime',
    'actual_arrival_datetime',
    'package_count',
    'delivery_count',
    'received_delivery_count',
    'last_modified',
    'data (JSON)',
    'synced_at'
]

# From Cannlytics Transfer model (cannlytics/metrc/models.py)
CANNLYTICS_TRANSFER_FIELDS = [
    'id',
    'manifest_number',
    'shipment_license_type',
    'shipper_facility_license_number',
    'shipper_facility_name',
    'name',
    'transporter_facility_license_number',
    'transporter_facility_name',
    'driver_name',
    'driver_occupational_license_number',
    'driver_vehicle_license_number',
    'vehicle_make',
    'vehicle_model',
    'vehicle_license_plate_number',
    'delivery_count',
    'received_delivery_count',
    'package_count',
    'received_package_count',
    'created_date_time',
    'received_date_time',
    'estimated_departure_date_time',
    'actual_departure_date_time',
    'estimated_arrival_date_time',
    'actual_arrival_date_time',
    'estimated_return_departure_date_time',
    'actual_return_departure_date_time',
    'estimated_return_arrival_date_time',
    'actual_return_arrival_date_time',
    'delivery_package_count',
    'delivery_received_package_count'
]

# From Cannlytics TransferDeliveryPackage (transfer packages endpoint)
DELIVERY_PACKAGE_FIELDS = [
    'PackageId',
    'PackageLabel',
    'PackageType',
    'SourceHarvestNames',
    'SourcePackageLabels',
    'ProductName',
    'ProductCategoryName',
    'ItemId',
    'ItemName',
    'ItemCategoryName',
    'ItemStrainName',
    'ItemUnitCbdPercent',
    'ItemUnitCbdContent',
    'ItemUnitCbdContentUnitOfMeasureName',
    'ItemUnitCbdContentDose',
    'ItemUnitThcPercent',
    'ItemUnitThcContent',
    'ItemUnitThcContentUnitOfMeasureName',
    'ItemUnitThcContentDose',
    'ItemUnitVolume',
    'ItemUnitVolumeUnitOfMeasureName',
    'ItemUnitWeight',
    'ItemUnitWeightUnitOfMeasureName',
    'ItemServingSize',
    'ItemSupplyDurationDays',
    'ItemUnitQuantity',
    'ItemUnitQuantityUnitOfMeasureName',
    'QuantityShipped',
    'QuantityReceived',
    'UnitOfMeasureName',
    'UnitOfMeasureAbbreviation',
    'PackagedDate',
    'GrossWeight',
    'GrossUnitOfWeightName',
    'GrossUnitOfWeightAbbreviation',
    'ReceivedDateTime',
    'WholesalePrice',  # KEY - only in wholesale endpoint
    'ShipperWholesalePrice',  # KEY
    'ReceiverWholesalePrice',  # KEY
    'IsTestingSample',
    'IsProcessValidationTestSample',
    'IsProductionBatch',
    'ProductionBatchNumber',
    'IsTradeSample',
    'IsOnHold',
    'ArchivedDate',
    'FinishedDate',
    'LastModified'
]

# =============================================================================
# MISSING FIELDS / OPPORTUNITIES
# =============================================================================

MISSING_FIELDS = {
    'transporter_details': {
        'fields': [
            'driver_name',
            'driver_occupational_license_number',
            'driver_vehicle_license_number',
            'phone_number_for_questions',
            'vehicle_make',
            'vehicle_model',
            'vehicle_license_plate_number',
            'is_layover'
        ],
        'endpoint': 'get_transfers_v2_deliveries_id_transporters',
        'business_value': 'Driver/vehicle tracking, compliance verification, route optimization',
        'table': 'New table: metrc_transfer_transporters (many-to-one with transfers)'
    },
    
    'return_trip_data': {
        'fields': [
            'estimated_return_departure_date_time',
            'actual_return_departure_date_time',
            'estimated_return_arrival_date_time',
            'actual_return_arrival_date_time'
        ],
        'endpoint': 'Root transfer object (may be in JSON already)',
        'business_value': 'Round-trip logistics, empty vehicle tracking',
        'table': 'Add columns to metrc_transfers'
    },
    
    'wholesale_pricing': {
        'fields': [
            'wholesale_price',
            'shipper_wholesale_price',
            'receiver_wholesale_price'
        ],
        'endpoint': 'Currently using /wholesale variant but not storing pricing',
        'business_value': 'Revenue tracking, intercompany pricing, COGS',
        'table': 'New table: metrc_transfer_package_pricing (link to packages)'
    },
    
    'lab_testing_requirements': {
        'fields': [
            'required_lab_test_batches'
        ],
        'endpoint': 'get_transfers_v2_deliveries_package_id_requiredlabtestbatches',
        'business_value': 'Compliance tracking, testing workflow',
        'table': 'New table: metrc_transfer_required_tests'
    },
    
    'received_timestamps': {
        'fields': [
            'received_date_time',
            'received_package_count',
            'delivery_received_package_count'
        ],
        'endpoint': 'Root transfer or delivery objects',
        'business_value': 'Actual vs estimated timing, inventory receipt tracking',
        'table': 'Add columns to metrc_transfers'
    }
}

# =============================================================================
# RECOMMENDED IMPLEMENTATION PRIORITY
# =============================================================================

PRIORITY_RECOMMENDATIONS = """
HIGH PRIORITY - Immediate Business Value:
========================================

1. TRANSPORTER DETAILS (/transfers/v2/deliveries/{id}/transporters)
   - Driver name, license, vehicle info
   - Phone number for logistics coordination
   - Actual departure/arrival for each leg
   - Business Case: Route tracking, driver compliance, coordination
   - Implementation: New table metrc_transfer_transporters
   
2. WHOLESALE PRICING (already fetching, need to store)
   - WholesalePrice, ShipperWholesalePrice, ReceiverWholesalePrice
   - Business Case: Revenue analysis, intercompany pricing, COGS tracking
   - Implementation: Add pricing columns to delivery packages or separate pricing table
   
3. RECEIVED TIMESTAMPS & COUNTS
   - ReceivedDateTime, ReceivedPackageCount per delivery
   - Business Case: Inventory reconciliation, timing analysis (actual vs estimated)
   - Implementation: Add received_date_time, received_package_count to transfers

MEDIUM PRIORITY - Enhanced Analytics:
====================================

4. HUB TRANSFERS (/transfers/v2/hub)
   - Multi-stop distribution transfers
   - Business Case: If doing hub distribution, critical. Otherwise skip.
   - Implementation: Same structure as incoming/outgoing
   
5. LAB TEST REQUIREMENTS (/transfers/v2/deliveries/package/{id}/requiredlabtestbatches)
   - Required testing for transferred packages
   - Business Case: Compliance workflow, testing cost tracking
   - Implementation: New table metrc_transfer_lab_requirements

LOW PRIORITY:
============

6. RETURN TRIP DATA
   - EstimatedReturnDepartureDateTime, ActualReturnArrivalDateTime, etc.
   - Business Case: Round-trip logistics (likely NULL for most operations)
   - Implementation: Add columns if analysis shows non-null values

7. TRANSFER DELIVERIES ENDPOINT (/transfers/v2/{id}/deliveries)
   - Alternative to embedded Deliveries array
   - Business Case: May provide more complete data than embedded array
   - Implementation: Compare vs embedded data, adopt if richer
"""

print("Metrc V2 Transfer Enrichment Analysis")
print("=" * 80)
print("\nCURRENT APPROACH:")
print("  - Fetching incoming/outgoing/rejected transfers")
print("  - Enriching with delivery packages (wholesale endpoint)")
print("  - Storing basic transfer metadata + full JSON")
print("\nKEY GAPS:")
print("  1. Transporter/driver details (compliance tracking)")
print("  2. Wholesale pricing (revenue analysis)")
print("  3. Received timestamps (reconciliation)")
print("  4. Lab test requirements (compliance)")
print("\nSee PRIORITY_RECOMMENDATIONS for implementation roadmap")
