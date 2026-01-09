"""
Comprehensive validation of all Metrc table parsing.
Checks for NULL columns that have data in JSON, indicating field name mismatches.
"""

import os
import psycopg2
import json
from dotenv import load_dotenv
from collections import defaultdict
from supabase_config import get_connection_string

load_dotenv()

# Supabase connection
conn = psycopg2.connect(get_connection_string())
cursor = conn.cursor()

def analyze_table(table_name):
    """Analyze a table for NULL columns and compare to JSON data"""
    print(f"\n{'='*80}")
    print(f"ANALYZING TABLE: {table_name}")
    print(f"{'='*80}")
    
    # Get column names and types
    cursor.execute(f"""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = '{table_name}' 
        AND table_schema = 'public'
        ORDER BY ordinal_position
    """)
    columns = cursor.fetchall()
    
    # Check if table has 'data' column
    has_data_column = any(col[0] == 'data' for col in columns)
    
    # Get total row count
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    total_rows = cursor.fetchone()[0]
    
    if total_rows == 0:
        print(f"⚠️  Table is empty")
        return
    
    print(f"\nTotal rows: {total_rows:,}")
    
    # Check NULL percentages for each column
    null_columns = []
    for col_name, col_type in columns:
        if col_name in ['id', 'created_at', 'synced_at', 'data']:
            continue
            
        cursor.execute(f"""
            SELECT COUNT(*) 
            FROM {table_name} 
            WHERE {col_name} IS NULL
        """)
        null_count = cursor.fetchone()[0]
        null_pct = (null_count / total_rows) * 100
        
        if null_pct > 50:  # More than 50% NULL is suspicious
            null_columns.append((col_name, null_count, null_pct))
    
    if not null_columns:
        print(f"✓ No columns with >50% NULL values")
        return
    
    print(f"\n⚠️  Found {len(null_columns)} columns with >50% NULL values:")
    for col_name, null_count, null_pct in null_columns:
        print(f"  - {col_name}: {null_count:,} NULL ({null_pct:.1f}%)")
    
    if not has_data_column:
        print(f"\n⚠️  Table doesn't have 'data' column - cannot validate against JSON")
        return
    
    # Sample JSON data to find potential field names
    cursor.execute(f"""
        SELECT data 
        FROM {table_name} 
        WHERE data IS NOT NULL 
        LIMIT 5
    """)
    
    samples = cursor.fetchall()
    if not samples:
        print(f"\n⚠️  No JSON data found to validate against")
        return
    
    # Analyze JSON structure
    print(f"\n🔍 Checking JSON data for missing fields...")
    json_fields = {}
    sample_values = {}
    
    for (json_data,) in samples:
        try:
            data = json.loads(json_data)
            for key, value in data.items():
                if key not in json_fields:
                    json_fields[key] = 0
                    sample_values[key] = value
                json_fields[key] += 1
                
            # Also check nested Item object (for packages)
            if 'Item' in data and isinstance(data['Item'], dict):
                for key, value in data['Item'].items():
                    nested_key = f"Item.{key}"
                    if nested_key not in json_fields:
                        json_fields[nested_key] = 0
                        sample_values[nested_key] = value
                    json_fields[nested_key] += 1
        except:
            continue
    
    # Try to match NULL columns to JSON fields
    print(f"\n🔎 Checking for field name mismatches:")
    mismatches_found = False
    
    for col_name, null_count, null_pct in null_columns:
        # Convert column name to potential JSON field names
        potential_matches = []
        
        # Try PascalCase
        pascal = ''.join(word.capitalize() for word in col_name.split('_'))
        if pascal in json_fields and sample_values.get(pascal) is not None:
            potential_matches.append((pascal, sample_values[pascal]))
        
        # Try with suffixes
        for suffix in ['Name', 'Number', 'Id', 'Date', 'Count', 'State', 'Type']:
            test_field = pascal + suffix
            if test_field in json_fields and sample_values.get(test_field) is not None:
                potential_matches.append((test_field, sample_values[test_field]))
        
        # Check Item.* nested fields
        item_field = f"Item.{pascal}"
        if item_field in json_fields and sample_values.get(item_field) is not None:
            potential_matches.append((item_field, sample_values[item_field]))
        
        if potential_matches:
            print(f"  ❌ {col_name} is NULL but data exists in JSON:")
            for field, value in potential_matches:
                value_str = str(value)[:50]
                print(f"      → {field}: {value_str}")
            mismatches_found = True
        else:
            # This might be legitimately NULL in the API
            print(f"  ✓ {col_name} ({null_pct:.1f}% NULL) - likely not in API")
    
    if not mismatches_found:
        print(f"  ✓ No field name mismatches detected")

# Main analysis
print("METRC TABLE PARSING VALIDATION")
print("Checking all tables for NULL columns that may have data in JSON...")

# Get all metrc tables
cursor.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name LIKE 'metrc_%'
    ORDER BY table_name
""")

tables = [row[0] for row in cursor.fetchall()]

print(f"\nFound {len(tables)} Metrc tables to analyze:")
for table in tables:
    print(f"  - {table}")

# Analyze each table
for table in tables:
    try:
        analyze_table(table)
    except Exception as e:
        print(f"\n❌ Error analyzing {table}: {e}")

cursor.close()
conn.close()

print(f"\n{'='*80}")
print("VALIDATION COMPLETE")
print(f"{'='*80}")
