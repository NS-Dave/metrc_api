"""
Demo: Package History Tracking System

Shows practical examples of tracking package journeys.
"""
import psycopg2
from supabase_config import get_connection_string

conn = psycopg2.connect(get_connection_string())
cursor = conn.cursor()

print("\n" + "="*70)
print("PACKAGE HISTORY TRACKING - DEMO")
print("="*70)

# Find a package that has changed recently
print("\n1. Find recently changed packages...")
cursor.execute("""
    SELECT DISTINCT label, change_type, valid_from
    FROM metrc_packages_history
    WHERE change_type != 'initial_snapshot'
      AND valid_from >= NOW() - INTERVAL '7 days'
    LIMIT 5
""")

recent_changes = cursor.fetchall()
if recent_changes:
    print("\nRecently changed packages:")
    for label, change_type, valid_from in recent_changes:
        print(f"  {label}: {change_type} at {valid_from}")
    demo_label = recent_changes[0][0]
else:
    # Use any package
    cursor.execute("SELECT label FROM metrc_packages LIMIT 1")
    demo_label = cursor.fetchone()[0]
    print(f"\nNo recent changes found. Using sample: {demo_label}")

print(f"\n{'='*70}")
print(f"TRACKING: {demo_label}")
print(f"{'='*70}")

# 2. Get complete timeline
print("\n2. COMPLETE TIMELINE:")
print("-" * 70)
cursor.execute("""
    SELECT 
        change_time,
        change_type,
        changed_fields,
        quantity,
        is_finished,
        is_archived,
        endpoint_source
    FROM get_package_timeline(%s)
""", (demo_label,))

timeline = cursor.fetchall()
for i, row in enumerate(timeline, 1):
    change_time, change_type, changed_fields, qty, finished, archived, endpoint = row
    print(f"\n  Entry {i}: {change_time}")
    print(f"    Type: {change_type}")
    if changed_fields:
        print(f"    Changed: {changed_fields}")
    print(f"    Quantity: {qty}, Finished: {finished}, Source: {endpoint}")

# 3. Current vs Historical state
print(f"\n{'='*70}")
print("3. STATE COMPARISON:")
print("-" * 70)

cursor.execute("""
    SELECT quantity, is_finished, is_archived, location_name, endpoint_source
    FROM metrc_packages
    WHERE label = %s
""", (demo_label,))

current = cursor.fetchone()
if current:
    curr_qty, curr_finished, curr_archived, curr_location, curr_endpoint = current
    print(f"\nCURRENT STATE:")
    print(f"  Quantity: {curr_qty}")
    print(f"  Finished: {curr_finished}")
    print(f"  Archived: {curr_archived}")
    print(f"  Location: {curr_location}")
    print(f"  Endpoint: {curr_endpoint}")

# Get first historical state
cursor.execute("""
    SELECT quantity, is_finished, is_archived, location_name, endpoint_source, valid_from
    FROM metrc_packages_history
    WHERE label = %s
    ORDER BY valid_from
    LIMIT 1
""", (demo_label,))

first = cursor.fetchone()
if first:
    first_qty, first_finished, first_archived, first_location, first_endpoint, first_time = first
    print(f"\nFIRST KNOWN STATE ({first_time.date()}):")
    print(f"  Quantity: {first_qty}")
    print(f"  Finished: {first_finished}")
    print(f"  Archived: {first_archived}")
    print(f"  Location: {first_location}")
    print(f"  Endpoint: {first_endpoint}")

# 4. Aggregate statistics
print(f"\n{'='*70}")
print("4. SYSTEM-WIDE STATISTICS:")
print("-" * 70)

# Total history entries
cursor.execute("SELECT COUNT(*) FROM metrc_packages_history")
total_history = cursor.fetchone()[0]

# Entries by change type
cursor.execute("""
    SELECT change_type, COUNT(*) as count
    FROM metrc_packages_history
    GROUP BY change_type
    ORDER BY count DESC
""")

print(f"\nTotal history entries: {total_history:,}")
print(f"\nBreakdown by change type:")
for change_type, count in cursor.fetchall():
    pct = (count / total_history * 100) if total_history > 0 else 0
    print(f"  {change_type:20} {count:>6,} ({pct:>5.1f}%)")

# Packages with state changes
cursor.execute("""
    SELECT COUNT(DISTINCT label)
    FROM metrc_packages_history
    WHERE change_type = 'state_change'
""")
state_change_count = cursor.fetchone()[0]
print(f"\nPackages that changed state: {state_change_count:,}")

# 5. Find active packages that will likely finish soon
print(f"\n{'='*70}")
print("5. PREDICTIVE INSIGHTS - Packages Likely to Finish Soon:")
print("-" * 70)

cursor.execute("""
    SELECT 
        p.label,
        p.quantity,
        p.location_name,
        p.packaged_date,
        COUNT(h.history_id) as change_count,
        MAX(h.valid_from) as last_change
    FROM metrc_packages p
    LEFT JOIN metrc_packages_history h ON p.label = h.label
    WHERE p.is_finished = false
      AND p.quantity > 0
      AND p.packaged_date < NOW() - INTERVAL '30 days'
    GROUP BY p.label, p.quantity, p.location_name, p.packaged_date
    HAVING COUNT(h.history_id) > 2  -- Has some history of changes
    ORDER BY p.packaged_date
    LIMIT 5
""")

print("\nOlder active packages with change history (candidates for finishing):")
for row in cursor.fetchall():
    label, qty, location, packaged, changes, last_change = row
    days_old = (cursor.execute("SELECT NOW()")[0] - packaged).days if packaged else 0
    print(f"\n  {label}")
    print(f"    Age: {days_old} days, Quantity: {qty}, Changes: {changes}")
    print(f"    Last changed: {last_change}")

# 6. Harvest reconciliation preview
print(f"\n{'='*70}")
print("6. HARVEST WEIGHT TRACKING PREVIEW:")
print("-" * 70)

cursor.execute("""
    SELECT DISTINCT source_harvest_names
    FROM metrc_packages
    WHERE source_harvest_names IS NOT NULL
      AND license_number = 'MC281599'
    LIMIT 1
""")

sample_harvest = cursor.fetchone()
if sample_harvest and sample_harvest[0]:
    harvest_name = sample_harvest[0].split(',')[0].strip()
    
    cursor.execute("""
        SELECT 
            label,
            quantity,
            is_finished,
            valid_from::date as snapshot_date
        FROM metrc_packages_history
        WHERE source_harvest_names LIKE %s
        ORDER BY label, valid_from
        LIMIT 10
    """, (f'%{harvest_name}%',))
    
    print(f"\nSample harvest: {harvest_name}")
    print(f"Package quantity snapshots:\n")
    
    current_label = None
    for label, qty, finished, snapshot_date in cursor.fetchall():
        if label != current_label:
            print(f"\n  {label}:")
            current_label = label
        status = "finished" if finished else "active"
        print(f"    {snapshot_date}: {qty}g ({status})")

cursor.close()
conn.close()

print(f"\n{'='*70}")
print("✓ DEMO COMPLETE")
print("="*70)
print("""
This system enables:
  1. Complete package journey tracking
  2. State change detection and analysis
  3. Quantity consumption monitoring
  4. Harvest weight reconciliation over time
  5. Predictive analytics for package lifecycle
  6. Compliance audit trails

Next: Run daily syncs to accumulate rich historical data!
""")
print("="*70)
