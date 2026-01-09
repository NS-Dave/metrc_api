#!/usr/bin/env python3
"""
Export Harvest Reconciliation to Excel

Exports SQL-based harvest reconciliation views to Excel spreadsheets
with multiple worksheets for different aspects of reconciliation.

Also fetches additional context from Metrc API:
- Package source harvest details (for complex packages)
- Adjustment reasons (for weight discrepancies)

Usage:
    python export_harvest_reconciliation.py --output reconciliation.xlsx
    python export_harvest_reconciliation.py --license MC281599 --with-api-context
"""

import psycopg2
from psycopg2.extras import DictCursor
import pandas as pd
from supabase_config import get_connection_string
from datetime import datetime
import argparse
from typing import Dict, List, Optional
import json


class HarvestReconciliationExporter:
    """Export harvest reconciliation data to Excel with API enrichment."""
    
    def __init__(self, license_number: str = 'MC281599'):
        self.conn = psycopg2.connect(get_connection_string())
        self.license_number = license_number
    
    @staticmethod
    def _remove_timezones(df: pd.DataFrame) -> pd.DataFrame:
        """Convert timezone-aware datetime columns to timezone-naive for Excel compatibility."""
        for col in df.select_dtypes(include=['datetimetz']).columns:
            df[col] = df[col].dt.tz_localize(None)
        return df
    
    def get_reconciliation_summary(self) -> pd.DataFrame:
        """Get main reconciliation summary."""
        query = """
            SELECT 
                harvest_name,
                harvest_type,
                harvest_strain,
                harvest_packaged_date,
                harvest_weight,
                simple_package_count,
                simple_total_weight,
                simple_active_count,
                simple_active_weight,
                simple_sale_count,
                simple_sale_weight,
                simple_internal_count,
                simple_internal_weight,
                complex_package_count,
                complex_total_weight,
                simple_discrepancy,
                simple_discrepancy_pct,
                reconciliation_status,
                has_complex_packages
            FROM v_harvest_reconciliation
            WHERE license_number = %s
            ORDER BY harvest_packaged_date DESC NULLS LAST
        """
        
        return pd.read_sql_query(query, self.conn, params=[self.license_number])
    
    def get_harvests_needing_review(self) -> pd.DataFrame:
        """Get harvests with issues."""
        query = """
            SELECT 
                harvest_name,
                harvest_strain,
                harvest_packaged_date,
                harvest_weight,
                simple_total_weight,
                simple_discrepancy,
                simple_discrepancy_pct,
                complex_package_count,
                complex_total_weight,
                reconciliation_status
            FROM v_harvests_needing_review
        """
        
        return pd.read_sql_query(query, self.conn)
    
    def get_complex_packages(self) -> pd.DataFrame:
        """Get all complex packages needing manual allocation."""
        query = """
            SELECT 
                label,
                product_name,
                quantity,
                unit_of_measure,
                source_harvest_names,
                source_harvest_count,
                package_status,
                packaged_date,
                finished_date,
                archived_date,
                transfer_type,
                destination_facility_name,
                shipped_date,
                manifest_number
            FROM v_complex_packages_detail
            ORDER BY packaged_date DESC
        """
        
        return pd.read_sql_query(query, self.conn)
    
    def get_harvest_detail(self, harvest_name: str) -> pd.DataFrame:
        """Get all packages for a specific harvest."""
        query = """
            SELECT 
                pd.label,
                pd.product_name,
                pd.quantity,
                pd.unit_of_measure,
                pd.source_harvest_names,
                pd.package_complexity,
                pd.package_status,
                pd.packaged_date,
                pd.finished_date,
                pd.archived_date,
                pd.transfer_type,
                pd.destination_facility_name,
                pd.shipped_date,
                pd.manifest_number
            FROM v_package_detail pd
            WHERE pd.license_number = %s
                AND %s = ANY(pd.source_harvest_array)
            ORDER BY pd.packaged_date
        """
        
        return pd.read_sql_query(query, self.conn, params=[self.license_number, harvest_name])
    
    def get_active_inventory_by_harvest(self) -> pd.DataFrame:
        """Get current active inventory grouped by harvest."""
        query = """
            SELECT 
                UNNEST(source_harvest_array) as harvest_name,
                COUNT(*) as package_count,
                SUM(quantity) as total_weight,
                MIN(packaged_date) as earliest_package,
                MAX(packaged_date) as latest_package,
                string_agg(DISTINCT product_name, '; ') as product_types
            FROM v_package_categorization
            WHERE license_number = %s
                AND package_status = 'active'
            GROUP BY harvest_name
            ORDER BY total_weight DESC
        """
        
        return pd.read_sql_query(query, self.conn, params=[self.license_number])
    
    def get_sales_by_harvest(self) -> pd.DataFrame:
        """Get sales grouped by harvest."""
        query = """
            SELECT 
                UNNEST(pd.source_harvest_array) as harvest_name,
                COUNT(DISTINCT pd.label) as packages_sold,
                SUM(pd.quantity_shipped) as total_sold_weight,
                MIN(pd.shipped_date) as first_sale,
                MAX(pd.shipped_date) as latest_sale,
                COUNT(DISTINCT pd.destination_facility_name) as customer_count
            FROM v_package_detail pd
            WHERE pd.license_number = %s
                AND pd.transfer_type = 'sale'
            GROUP BY harvest_name
            ORDER BY total_sold_weight DESC
        """
        
        return pd.read_sql_query(query, self.conn, params=[self.license_number])
    
    def export_to_excel(self, output_file: str):
        """Export all reconciliation data to Excel with multiple sheets."""
        print(f"Exporting harvest reconciliation to {output_file}...")
        
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # Main reconciliation summary
            print("  - Reconciliation Summary...")
            df_summary = self._remove_timezones(self.get_reconciliation_summary())
            df_summary.to_excel(writer, sheet_name='Reconciliation Summary', index=False)
            
            # Harvests needing review
            print("  - Harvests Needing Review...")
            df_review = self._remove_timezones(self.get_harvests_needing_review())
            df_review.to_excel(writer, sheet_name='Needs Review', index=False)
            
            # Complex packages
            print("  - Complex Packages...")
            df_complex = self._remove_timezones(self.get_complex_packages())
            df_complex.to_excel(writer, sheet_name='Complex Packages', index=False)
            
            # Active inventory by harvest
            print("  - Active Inventory by Harvest...")
            df_active = self._remove_timezones(self.get_active_inventory_by_harvest())
            df_active.to_excel(writer, sheet_name='Active Inventory', index=False)
            
            # Sales by harvest
            print("  - Sales by Harvest...")
            df_sales = self._remove_timezones(self.get_sales_by_harvest())
            df_sales.to_excel(writer, sheet_name='Sales by Harvest', index=False)
        
        print(f"\n✓ Export complete: {output_file}")
        print(f"  Summary: {len(df_summary)} harvests")
        print(f"  Needs Review: {len(df_review)} harvests")
        print(f"  Complex Packages: {len(df_complex)} packages")
    
    def export_harvest_detail(self, harvest_name: str, output_file: str):
        """Export detailed breakdown for a single harvest."""
        print(f"Exporting detail for harvest: {harvest_name}")
        
        df_detail = self.get_harvest_detail(harvest_name)
        df_detail.to_excel(output_file, sheet_name=harvest_name[:31], index=False)
        
        print(f"✓ Exported {len(df_detail)} packages to {output_file}")
    
    def close(self):
        if self.conn:
            self.conn.close()


class MetrcAPIContext:
    """Fetch additional context from Metrc API for reconciliation."""
    
    def __init__(self):
        from client import MetrcClient
        self.client = MetrcClient()
    
    def get_package_source_harvests(self, package_id: int, license_number: str) -> List[Dict]:
        """
        Get source harvest details for a package.
        Uses Metrc's GetPackageSourceHarvestById endpoint.
        """
        endpoint = f'packages/v2/{package_id}/source/harvests'
        
        try:
            result = self.client.get(endpoint, license_number=license_number)
            return result if isinstance(result, list) else []
        except Exception as e:
            print(f"Error fetching source harvests for package {package_id}: {e}")
            return []
    
    def get_adjustment_reasons(self, license_number: str) -> List[Dict]:
        """
        Get list of package adjustment reasons.
        Uses Metrc's GetAdjustmentReasons endpoint.
        """
        endpoint = 'packages/v2/adjust/reasons'
        
        try:
            result = self.client.get(endpoint, license_number=license_number)
            return result if isinstance(result, list) else []
        except Exception as e:
            print(f"Error fetching adjustment reasons: {e}")
            return []
    
    def enrich_complex_packages(self, df_complex: pd.DataFrame, license_number: str) -> pd.DataFrame:
        """
        Enrich complex package data with source harvest details from API.
        """
        print("Fetching source harvest details from Metrc API...")
        
        # Get package IDs from database
        conn = psycopg2.connect(get_connection_string())
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        labels = df_complex['label'].tolist()
        placeholders = ','.join(['%s'] * len(labels))
        
        cursor.execute(f"""
            SELECT label, id 
            FROM metrc_packages 
            WHERE label IN ({placeholders})
        """, labels)
        
        label_to_id = {row['label']: row['id'] for row in cursor.fetchall()}
        cursor.close()
        conn.close()
        
        # Fetch source harvest details for each package
        source_harvest_details = []
        for idx, row in df_complex.iterrows():
            label = row['label']
            package_id = label_to_id.get(label)
            
            if package_id:
                harvests = self.get_package_source_harvests(package_id, license_number)
                if harvests:
                    # Create a formatted string of harvest details
                    details = []
                    for h in harvests:
                        weight = h.get('Weight', 0)
                        unit = h.get('UnitOfWeight', 'g')
                        harvest_name = h.get('HarvestName', 'Unknown')
                        details.append(f"{harvest_name}: {weight}{unit}")
                    source_harvest_details.append('; '.join(details))
                else:
                    source_harvest_details.append('No API data')
            else:
                source_harvest_details.append('Package ID not found')
        
        df_complex['api_source_harvest_details'] = source_harvest_details
        return df_complex


def main():
    parser = argparse.ArgumentParser(description='Export Harvest Reconciliation to Excel')
    parser.add_argument('--output', type=str, default='harvest_reconciliation.xlsx',
                       help='Output Excel file (default: harvest_reconciliation.xlsx)')
    parser.add_argument('--license', type=str, default='MC281599',
                       help='License number (default: MC281599)')
    parser.add_argument('--harvest', type=str,
                       help='Export detail for specific harvest')
    parser.add_argument('--with-api-context', action='store_true',
                       help='Enrich with additional context from Metrc API (slower)')
    
    args = parser.parse_args()
    
    exporter = HarvestReconciliationExporter(license_number=args.license)
    
    try:
        if args.harvest:
            # Export single harvest detail
            exporter.export_harvest_detail(args.harvest, args.output)
        else:
            # Export full reconciliation
            if args.with_api_context:
                print("Enriching with Metrc API context...")
                api = MetrcAPIContext()
                
                # Get adjustment reasons for reference
                print("Fetching adjustment reasons...")
                reasons = api.get_adjustment_reasons(args.license)
                if reasons:
                    df_reasons = pd.DataFrame(reasons)
                    reasons_file = args.output.replace('.xlsx', '_adjustment_reasons.xlsx')
                    df_reasons.to_excel(reasons_file, index=False)
                    print(f"  ✓ Saved adjustment reasons to {reasons_file}")
                
                # Enrich complex packages
                df_complex = exporter.get_complex_packages()
                if len(df_complex) > 0:
                    df_complex_enriched = api.enrich_complex_packages(df_complex, args.license)
                    complex_file = args.output.replace('.xlsx', '_complex_enriched.xlsx')
                    df_complex_enriched.to_excel(complex_file, index=False)
                    print(f"  ✓ Saved enriched complex packages to {complex_file}")
            
            # Standard export
            exporter.export_to_excel(args.output)
    
    finally:
        exporter.close()


if __name__ == '__main__':
    main()
