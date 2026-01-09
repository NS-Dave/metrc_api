"""
Example usage scripts for Metrc API client.
Demonstrates common operations for Cultivation and Processing.
"""
from datetime import datetime, timedelta
from config import MetrcConfig
from client import MetrcClient
from cultivation import CultivationClient
from processing import ProcessingClient
from utils import DateUtils, DataTransformUtils


def example_basic_connection():
    """Example: Test basic connection and authentication."""
    print("=== Testing Connection ===")
    
    # Create config from environment variables
    config = MetrcConfig.from_env()
    
    # Create client
    client = MetrcClient(config)
    
    # Test connection
    if client.test_connection():
        print("✓ Connection successful!")
        
        # Get facilities
        facilities = client.get_facilities()
        print(f"\nFound {len(facilities)} facilities:")
        for fac in facilities:
            print(f"  - {fac.get('Name')} ({fac.get('License', {}).get('Number')})")
    else:
        print("✗ Connection failed")


def example_cultivation_workflow():
    """Example: Complete cultivation workflow."""
    print("\n=== Cultivation Workflow ===")
    
    config = MetrcConfig.from_env()
    client = MetrcClient(config)
    cultivation = CultivationClient(client)
    
    # 1. Get active strains
    print("\n1. Getting active strains...")
    strains = cultivation.get_strains()
    print(f"   Found {len(strains)} strains")
    for strain in strains[:3]:  # Show first 3
        print(f"   - {strain.get('Name')}")
    
    # 2. Get vegetative plants
    print("\n2. Getting vegetative plants...")
    veg_plants = cultivation.get_plants(phase='vegetative')
    print(f"   Found {len(veg_plants)} vegetative plants")
    
    # 3. Get flowering plants
    print("\n3. Getting flowering plants...")
    flower_plants = cultivation.get_plants(phase='flowering')
    print(f"   Found {len(flower_plants)} flowering plants")
    
    # 4. Get active harvests
    print("\n4. Getting active harvests...")
    harvests = cultivation.get_harvests(status='active')
    print(f"   Found {len(harvests)} active harvests")
    
    # 5. Get plant batches
    print("\n5. Getting plant batches...")
    batches = cultivation.get_plant_batches(status='active')
    print(f"   Found {len(batches)} active plant batches")


def example_processing_workflow():
    """Example: Processing operations."""
    print("\n=== Processing Workflow ===")
    
    config = MetrcConfig.from_env()
    client = MetrcClient(config)
    processing = ProcessingClient(client)
    
    # 1. Get active packages
    print("\n1. Getting active packages...")
    packages = processing.get_packages(status='active')
    print(f"   Found {len(packages)} active packages")
    
    # 2. Get items (products)
    print("\n2. Getting items...")
    items = processing.get_items()
    print(f"   Found {len(items)} items")
    for item in items[:5]:  # Show first 5
        print(f"   - {item.get('Name')}")
    
    # 3. Get locations
    print("\n3. Getting locations...")
    locations = processing.get_locations()
    print(f"   Found {len(locations)} locations")
    for loc in locations[:5]:  # Show first 5
        print(f"   - {loc.get('Name')}")
    
    # 4. Get incoming transfers
    print("\n4. Getting incoming transfers...")
    transfers = processing.get_incoming_transfers()
    print(f"   Found {len(transfers)} incoming transfers")


def example_incremental_sync():
    """Example: Incremental data sync using LastModified."""
    print("\n=== Incremental Sync Example ===")
    
    config = MetrcConfig.from_env()
    client = MetrcClient(config)
    cultivation = CultivationClient(client)
    processing = ProcessingClient(client)
    
    # Get data modified in last hour (with 5-minute buffer)
    start_time, end_time = DateUtils.get_sync_window(hours=1, buffer_minutes=5)
    
    print(f"\nSyncing data from {start_time} to {end_time}")
    
    # Get modified plants
    print("\n1. Checking for modified plants...")
    modified_plants = cultivation.get_plants(
        phase='vegetative',
        last_modified_start=start_time,
        last_modified_end=end_time
    )
    print(f"   Found {len(modified_plants)} modified vegetative plants")
    
    # Get modified packages
    print("\n2. Checking for modified packages...")
    modified_packages = processing.get_packages(
        status='active',
        last_modified_start=start_time,
        last_modified_end=end_time
    )
    print(f"   Found {len(modified_packages)} modified packages")
    
    # Get modified harvests
    print("\n3. Checking for modified harvests...")
    modified_harvests = cultivation.get_harvests(
        status='active',
        last_modified_start=start_time,
        last_modified_end=end_time
    )
    print(f"   Found {len(modified_harvests)} modified harvests")


def example_data_analysis():
    """Example: Analyzing and grouping data."""
    print("\n=== Data Analysis Example ===")
    
    config = MetrcConfig.from_env()
    client = MetrcClient(config)
    cultivation = CultivationClient(client)
    
    # Get all vegetative plants
    print("\n1. Getting plants for analysis...")
    plants = cultivation.get_plants(phase='vegetative')
    print(f"   Total plants: {len(plants)}")
    
    # Group by strain
    print("\n2. Grouping by strain...")
    by_strain = DataTransformUtils.group_by_strain(plants)
    for strain_name, strain_plants in by_strain.items():
        print(f"   {strain_name}: {len(strain_plants)} plants")
    
    # Get packages and analyze
    processing = ProcessingClient(client)
    packages = processing.get_packages(status='active')
    
    print(f"\n3. Analyzing {len(packages)} packages...")
    
    # Calculate total quantities by item
    by_item = {}
    for pkg in packages:
        item_name = pkg.get('Item', {}).get('Name', 'Unknown')
        quantity = pkg.get('Quantity', 0)
        
        if item_name not in by_item:
            by_item[item_name] = {'count': 0, 'total_quantity': 0}
        
        by_item[item_name]['count'] += 1
        by_item[item_name]['total_quantity'] += quantity
    
    print("\n   Inventory by item:")
    for item_name, stats in by_item.items():
        print(f"   - {item_name}: {stats['count']} packages, "
              f"total quantity: {stats['total_quantity']:.2f}")


def example_create_strain():
    """Example: Create a new strain."""
    print("\n=== Create Strain Example ===")
    
    config = MetrcConfig.from_env()
    client = MetrcClient(config)
    cultivation = CultivationClient(client)
    
    # Define new strain
    new_strains = [
        {
            "Name": "Example Strain",
            "TestingStatus": "None",
            "ThcLevel": 0.20,
            "CbdLevel": 0.05,
            "IndicaPercentage": 60.0,
            "SativaPercentage": 40.0
        }
    ]
    
    print("\nCreating strain: Example Strain")
    print("Note: This will fail if strain already exists")
    
    try:
        result = cultivation.create_strains(new_strains)
        print("✓ Strain created successfully!")
    except Exception as e:
        print(f"✗ Error creating strain: {e}")


def example_create_plant_batch():
    """Example: Create plant batch from package."""
    print("\n=== Create Plant Batch Example ===")
    
    config = MetrcConfig.from_env()
    client = MetrcClient(config)
    cultivation = CultivationClient(client)
    
    # Define new plant batch
    # NOTE: You'll need to update these values with real data
    new_batch = [
        {
            "Name": "Example Batch 12-18",
            "Type": "Clone",
            "Count": 10,
            "Strain": "Example Strain",  # Must exist
            "Location": "Propagation Room",  # Must exist
            "Item": "Clone Item",  # Must exist
            "PatientLicenseNumber": None,
            "ActualDate": DateUtils.date_only(datetime.now())
        }
    ]
    
    print("\nCreating plant batch from package...")
    print("Note: Update values with your actual strain, location, and item names")
    
    try:
        result = cultivation.create_plant_batches_from_packages(new_batch)
        print("✓ Plant batch created successfully!")
    except Exception as e:
        print(f"✗ Error creating plant batch: {e}")


def example_harvest_plants():
    """Example: Harvest plants."""
    print("\n=== Harvest Plants Example ===")
    
    config = MetrcConfig.from_env()
    client = MetrcClient(config)
    cultivation = CultivationClient(client)
    
    # Get flowering plants that are ready
    flowering = cultivation.get_plants(phase='flowering')
    
    if not flowering:
        print("No flowering plants found to harvest")
        return
    
    print(f"\nFound {len(flowering)} flowering plants")
    print("Example harvest data structure:")
    
    # Example harvest (not actually executed)
    example_harvest = {
        "Plant": "PLANT_TAG_HERE",  # Replace with actual plant tag
        "Weight": 100.5,
        "UnitOfWeight": "Grams",
        "DryingLocation": "Drying Room A",
        "HarvestName": f"Harvest-{datetime.now().strftime('%Y%m%d')}",
        "PatientLicenseNumber": None,
        "ActualDate": DateUtils.date_only(datetime.now())
    }
    
    print(f"\n{example_harvest}")
    print("\nNote: Update Plant tag and other values before executing")


if __name__ == "__main__":
    """Run examples."""
    
    print("Metrc API Examples")
    print("=" * 50)
    print("\nMake sure environment variables are set:")
    print("  - METRC_SOFTWARE_API_KEY")
    print("  - METRC_USER_API_KEY")
    print("  - METRC_LICENSE_NUMBER (optional)")
    print("=" * 50)
    
    try:
        # Test connection first
        example_basic_connection()
        
        # Run other examples
        # Uncomment the ones you want to run:
        
        # example_cultivation_workflow()
        # example_processing_workflow()
        # example_incremental_sync()
        # example_data_analysis()
        
        # BE CAREFUL with create operations:
        # example_create_strain()
        # example_create_plant_batch()
        # example_harvest_plants()
        
    except ValueError as e:
        print(f"\n✗ Configuration error: {e}")
        print("\nPlease set required environment variables")
    except Exception as e:
        print(f"\n✗ Error: {e}")
