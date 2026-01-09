#!/usr/bin/env python3
"""
Harvest Production Reconciliation Tool (Supabase Version)

Reconciles harvest packaged weight against actual packages in inventory and sales.

Business Rules:
1. Active Packages = finished_date IS NULL AND archived_date IS NULL
2. Sale Transfers = shipment_type IN ('Unaffiliated Transfer', 'Affiliated Transfer') 
                    AND destination_facility_name != '140 Industrial Road, LLC'
3. Each harvest's total_packaged_weight should equal sum of all related packages

Complexity Handling:
- Simple packages: Single source harvest (auto-reconcile)
- Complex packages: Multiple source harvests (flag for manual allocation)

Philosophy: Transparency over automation. Show all steps, allow review.
"""

import psycopg2
from psycopg2.extras import DictCursor
from supabase_config import get_connection_string
from datetime import datetime
import json
from typing import Dict, List, Optional
from collections import defaultdict


class HarvestReconciliationTool:
    """Reconcile harvest production with package inventory and sales."""
    
    def __init__(self):
        self.conn = psycopg2.connect(get_connection_string())
    
    def get_harvests(self, license_number: str = 'MC281599', 
                     start_date: Optional[str] = None,
                     end_date: Optional[str] = None) -> List[Dict]:
        """Get harvests with optional date filtering."""
        cursor = self.conn.cursor(cursor_factory=DictCursor)
        
        query = """
            SELECT 
                id,
                harvest_name,
                harvest_type,
                source_strain_names,
                current_weight,
                unit_of_weight,
                total_packaged_weight,
                packaged_date,
                finished_date,
                is_finished
            FROM metrc_harvests
            WHERE license_number = %s
        """
        
        params = [license_number]
        
        if start_date:
            query += " AND packaged_date >= %s"
            params.append(start_date)
        
        if end_date:
            query += " AND packaged_date <= %s"
            params.append(end_date)
        
        query += " ORDER BY packaged_date DESC"
        
        cursor.execute(query, params)
        harvests = [dict(row) for row in cursor.fetchall()]
        cursor.close()
        
        return harvests
    
    def get_harvest_packages(self, harvest_name: str, license_number: str = 'MC281599') -> Dict:
        """
        Get all packages for a harvest, categorized by complexity and status.
        
        Returns:
            {
                'simple_active': [...],      # Single harvest, in inventory
                'simple_finished': [...],    # Single harvest, finished/archived
                'complex': [...],            # Multiple harvests (needs manual allocation)
                'summary': {...}             # Counts and weights
            }
        """
        cursor = self.conn.cursor(cursor_factory=DictCursor)
        
        # Get all packages that include this harvest in source_harvest_names
        # Note: source_harvest_names can be a comma-separated list
        cursor.execute("""
            SELECT 
                id,
                label,
                product_name,
                quantity,
                unit_of_measure,
                source_harvest_names,
                packaged_date,
                finished_date,
                archived_date,
                last_modified
            FROM metrc_packages
            WHERE license_number = %s
                AND source_harvest_names LIKE %s
            ORDER BY packaged_date
        """, (license_number, f'%{harvest_name}%'))
        
        all_packages = [dict(row) for row in cursor.fetchall()]
        
        # Categorize packages
        simple_active = []
        simple_finished = []
        complex_packages = []
        
        for pkg in all_packages:
            source_harvests = [h.strip() for h in (pkg['source_harvest_names'] or '').split(',') if h.strip()]
            
            # Determine if simple (single harvest) or complex (multiple harvests)
            is_simple = len(source_harvests) == 1 and source_harvests[0] == harvest_name
            
            # Active = finished_date IS NULL AND archived_date IS NULL
            is_active = pkg['finished_date'] is None and pkg['archived_date'] is None
            
            if not is_simple:
                # Complex package - needs manual allocation
                complex_packages.append({
                    **pkg,
                    'harvest_count': len(source_harvests),
                    'all_harvests': source_harvests
                })
            elif is_active:
                # Simple active package
                simple_active.append(pkg)
            else:
                # Simple but finished/archived
                simple_finished.append(pkg)
        
        # Calculate summary
        simple_active_weight = sum(float(p['quantity'] or 0) for p in simple_active)
        simple_finished_weight = sum(float(p['quantity'] or 0) for p in simple_finished)
        complex_weight = sum(float(p['quantity'] or 0) for p in complex_packages)
        
        cursor.close()
        
        return {
            'simple_active': simple_active,
            'simple_finished': simple_finished,
            'complex': complex_packages,
            'summary': {
                'simple_active_count': len(simple_active),
                'simple_active_weight': simple_active_weight,
                'simple_finished_count': len(simple_finished),
                'simple_finished_weight': simple_finished_weight,
                'complex_count': len(complex_packages),
                'complex_weight': complex_weight,
                'total_simple_weight': simple_active_weight + simple_finished_weight,
                'total_packages': len(all_packages)
            }
        }
    
    def get_package_transfers(self, package_labels: List[str], license_number: str = 'MC281599') -> Dict:
        """
        Get transfer details for packages.
        
        Sale Transfer = shipment_type IN ('Unaffiliated Transfer', 'Affiliated Transfer')
                       AND destination_facility_name != '140 Industrial Road, LLC'
        """
        if not package_labels:
            return {'sale_transfers': [], 'internal_transfers': [], 'not_found_in_transfers': []}
        
        cursor = self.conn.cursor(cursor_factory=DictCursor)
        
        # Get transfer packages for these labels
        cursor.execute("""
            SELECT DISTINCT
                tp.package_label,
                tp.quantity_shipped,
                tp.unit_of_measure_name,
                t.id as transfer_id,
                t.manifest_number,
                t.shipment_type_name,
                t.destination_facility_name,
                t.shipper_facility_name,
                t.shipped_date,
                t.direction
            FROM metrc_transfer_packages tp
            JOIN metrc_transfers t ON tp.transfer_id = t.id
            WHERE tp.package_label = ANY(%s)
                AND t.license_number = %s
            ORDER BY t.shipped_date
        """, (package_labels, license_number))
        
        transfers = [dict(row) for row in cursor.fetchall()]
        cursor.close()
        
        # Categorize transfers
        sale_transfers = []
        internal_transfers = []
        found_labels = set()
        
        for transfer in transfers:
            found_labels.add(transfer['package_label'])
            
            # Check if it's a sale transfer
            is_sale = (
                transfer['shipment_type_name'] in ('Unaffiliated Transfer', 'Affiliated Transfer')
                and transfer['destination_facility_name'] != '140 Industrial Road, LLC'
            )
            
            if is_sale:
                sale_transfers.append(transfer)
            else:
                internal_transfers.append(transfer)
        
        # Find packages not in any transfer
        not_found = [label for label in package_labels if label not in found_labels]
        
        return {
            'sale_transfers': sale_transfers,
            'internal_transfers': internal_transfers,
            'not_found_in_transfers': not_found
        }
    
    def reconcile_harvest(self, harvest_name: str, license_number: str = 'MC281599') -> Dict:
        """
        Complete reconciliation for a single harvest.
        
        Returns transparent breakdown showing:
        - Harvest total packaged weight
        - Simple packages (active inventory)
        - Simple packages (finished/sold)
        - Complex packages (need manual allocation)
        - Transfer categorization
        - Discrepancy analysis
        """
        # Get harvest details
        cursor = self.conn.cursor(cursor_factory=DictCursor)
        cursor.execute("""
            SELECT * FROM metrc_harvests 
            WHERE harvest_name = %s AND license_number = %s
        """, (harvest_name, license_number))
        
        harvest = cursor.fetchone()
        if not harvest:
            return {'error': f'Harvest {harvest_name} not found'}
        
        harvest = dict(harvest)
        cursor.close()
        
        # Get all packages
        packages = self.get_harvest_packages(harvest_name, license_number)
        
        # Get transfer details for finished packages
        simple_finished_labels = [p['label'] for p in packages['simple_finished']]
        transfer_details = self.get_package_transfers(simple_finished_labels, license_number)
        
        # Calculate weights
        harvest_weight = float(harvest['total_packaged_weight'] or 0)
        
        # Active inventory
        active_weight = packages['summary']['simple_active_weight']
        active_count = packages['summary']['simple_active_count']
        
        # Sales (packages in external transfers)
        sale_weight = sum(float(t['quantity_shipped'] or 0) for t in transfer_details['sale_transfers'])
        sale_count = len(transfer_details['sale_transfers'])
        
        # Internal transfers
        internal_weight = sum(float(t['quantity_shipped'] or 0) for t in transfer_details['internal_transfers'])
        internal_count = len(transfer_details['internal_transfers'])
        
        # Finished but not in transfers (might be destroyed, consumed, etc.)
        not_transferred_count = len(transfer_details['not_found_in_transfers'])
        
        # Simple totals
        simple_total = packages['summary']['total_simple_weight']
        simple_count = packages['summary']['simple_active_count'] + packages['summary']['simple_finished_count']
        
        # Complex packages
        complex_weight = packages['summary']['complex_weight']
        complex_count = packages['summary']['complex_count']
        
        # Discrepancy (simple packages only - complex need manual allocation)
        simple_discrepancy = harvest_weight - simple_total
        discrepancy_pct = (simple_discrepancy / harvest_weight * 100) if harvest_weight > 0 else 0
        
        return {
            'harvest': {
                'name': harvest.get('harvest_name'),
                'id': harvest.get('id'),
                'harvest_type': harvest.get('harvest_type'),
                'strain': harvest.get('source_strain_names'),
                'total_packaged_weight': harvest_weight,
                'unit_of_weight': harvest.get('unit_of_weight'),
                'packaged_date': harvest.get('packaged_date').isoformat() if harvest.get('packaged_date') else None,
                'is_finished': harvest.get('is_finished')
            },
            'breakdown': {
                'simple_packages': {
                    'active_inventory': {
                        'count': active_count,
                        'weight': active_weight,
                        'packages': packages['simple_active']
                    },
                    'finished_or_archived': {
                        'sold_externally': {
                            'count': sale_count,
                            'weight': sale_weight,
                            'transfers': transfer_details['sale_transfers']
                        },
                        'internal_transfers': {
                            'count': internal_count,
                            'weight': internal_weight,
                            'transfers': transfer_details['internal_transfers']
                        },
                        'not_in_transfers': {
                            'count': not_transferred_count,
                            'labels': transfer_details['not_found_in_transfers']
                        }
                    },
                    'total': {
                        'count': simple_count,
                        'weight': simple_total
                    }
                },
                'complex_packages': {
                    'count': complex_count,
                    'weight': complex_weight,
                    'packages': packages['complex'],
                    'note': 'Multiple source harvests - require manual allocation'
                }
            },
            'reconciliation': {
                'harvest_weight': harvest_weight,
                'simple_weight': simple_total,
                'complex_weight': complex_weight,
                'simple_discrepancy': simple_discrepancy,
                'discrepancy_pct': discrepancy_pct,
                'status': 'OK' if abs(simple_discrepancy) < 1.0 else 'REVIEW_NEEDED',
                'has_complex': complex_count > 0,
                'needs_manual_allocation': complex_count > 0
            }
        }
    
    def print_harvest_detail(self, result: Dict, show_packages: bool = False):
        """Print detailed reconciliation for a single harvest."""
        print("\n" + "=" * 100)
        print(f"HARVEST RECONCILIATION: {result['harvest']['name']}")
        print("=" * 100)
        
        h = result['harvest']
        print(f"\nHarvest Info:")
        print(f"  ID: {h['id']}")
        print(f"  Type: {h['harvest_type']}")
        print(f"  Strain: {h['strain']}")
        print(f"  Packaged: {h['packaged_date']}")
        print(f"  Total Packaged Weight: {h['total_packaged_weight']:.2f} {h['unit_of_weight']}")
        
        b = result['breakdown']
        s = b['simple_packages']
        
        print(f"\nSimple Packages (Single Source Harvest):")
        print(f"  Active Inventory:")
        print(f"    Count: {s['active_inventory']['count']}")
        print(f"    Weight: {s['active_inventory']['weight']:.2f}g")
        
        print(f"  Finished/Archived:")
        print(f"    Sold Externally: {s['finished_or_archived']['sold_externally']['count']} packages, {s['finished_or_archived']['sold_externally']['weight']:.2f}g")
        print(f"    Internal Transfers: {s['finished_or_archived']['internal_transfers']['count']} packages, {s['finished_or_archived']['internal_transfers']['weight']:.2f}g")
        print(f"    Not in Transfers: {s['finished_or_archived']['not_in_transfers']['count']} packages")
        
        print(f"  Total Simple: {s['total']['count']} packages, {s['total']['weight']:.2f}g")
        
        c = b['complex_packages']
        if c['count'] > 0:
            print(f"\nComplex Packages (Multiple Source Harvests - MANUAL ALLOCATION NEEDED):")
            print(f"  Count: {c['count']}")
            print(f"  Weight: {c['weight']:.2f}g")
        
        r = result['reconciliation']
        print(f"\nReconciliation:")
        print(f"  Harvest Weight: {r['harvest_weight']:.2f}g")
        print(f"  Simple Packages: {r['simple_weight']:.2f}g")
        print(f"  Complex Packages: {r['complex_weight']:.2f}g")
        print(f"  Simple Discrepancy: {r['simple_discrepancy']:.2f}g ({r['discrepancy_pct']:.2f}%)")
        print(f"  Status: {r['status']}")
        
        if show_packages:
            if s['active_inventory']['count'] > 0:
                print(f"\nActive Inventory Details:")
                for pkg in s['active_inventory']['packages']:
                    print(f"  {pkg['label']}: {pkg['product_name']} - {pkg['quantity']:.2f} {pkg['unit_of_measure']}")
            
            if s['finished_or_archived']['sold_externally']['count'] > 0:
                print(f"\nSold Externally:")
                for t in s['finished_or_archived']['sold_externally']['transfers']:
                    print(f"  {t['package_label']}: {t['quantity_shipped']:.2f}g -> {t['destination_facility_name']} on {t['shipped_date']}")
            
            if c['count'] > 0:
                print(f"\nComplex Packages (Manual Allocation Required):")
                for pkg in c['packages']:
                    print(f"  {pkg['label']}: {pkg['product_name']} - {pkg['quantity']:.2f} {pkg['unit_of_measure']}")
                    print(f"    Sources ({pkg['harvest_count']}): {', '.join(pkg['all_harvests'])}")
        
        print("=" * 100)
    
    def generate_summary_report(self, license_number: str = 'MC281599',
                                start_date: Optional[str] = None,
                                end_date: Optional[str] = None) -> List[Dict]:
        """Generate reconciliation for multiple harvests."""
        harvests = self.get_harvests(license_number, start_date, end_date)
        
        results = []
        for harvest in harvests:
            try:
                result = self.reconcile_harvest(harvest['harvest_name'], license_number)
                results.append(result)
            except Exception as e:
                print(f"Error processing {harvest['harvest_name']}: {e}")
        
        return results
    
    def print_summary(self, results: List[Dict]):
        """Print summary table of all reconciliations."""
        print("\n" + "=" * 120)
        print("HARVEST RECONCILIATION SUMMARY")
        print("=" * 120)
        
        print(f"\n{'Harvest':<45} {'Total':<10} {'Active':<10} {'Sold':<10} {'Complex':<8} {'Discrep':<10} {'Status':<15}")
        print("-" * 120)
        
        for result in results:
            if 'error' in result:
                continue
            
            h = result['harvest']
            s = result['breakdown']['simple_packages']
            c = result['breakdown']['complex_packages']
            r = result['reconciliation']
            
            status = r['status']
            if c['count'] > 0:
                status += ' +COMPLEX'
            
            print(f"{h['name']:<45} "
                  f"{h['total_packaged_weight']:>8.1f}g "
                  f"{s['active_inventory']['weight']:>8.1f}g "
                  f"{s['finished_or_archived']['sold_externally']['weight']:>8.1f}g "
                  f"{c['count']:>6} "
                  f"{r['simple_discrepancy']:>8.1f}g "
                  f"{status:<15}")
        
        print("=" * 120 + "\n")
    
    def close(self):
        if self.conn:
            self.conn.close()


def main():
    """CLI for harvest reconciliation."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Harvest Production Reconciliation Tool')
    parser.add_argument('--harvest', type=str, help='Specific harvest name')
    parser.add_argument('--days', type=int, help='Last N days')
    parser.add_argument('--start', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--packages', action='store_true', help='Show package details')
    parser.add_argument('--export', type=str, help='Export to JSON file')
    
    args = parser.parse_args()
    
    recon = HarvestReconciliationTool()
    
    try:
        if args.harvest:
            # Single harvest detail
            result = recon.reconcile_harvest(args.harvest)
            
            if 'error' in result:
                print(f"Error: {result['error']}")
                return
            
            recon.print_harvest_detail(result, show_packages=args.packages)
            
            if args.export:
                with open(args.export, 'w') as f:
                    json.dump(result, f, indent=2, default=str)
                print(f"\nExported to {args.export}")
        
        else:
            # Summary report
            from datetime import datetime, timedelta
            
            start_date = args.start
            end_date = args.end
            
            if args.days:
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=args.days)).strftime('%Y-%m-%d')
            
            results = recon.generate_summary_report(
                license_number='MC281599',
                start_date=start_date,
                end_date=end_date
            )
            
            recon.print_summary(results)
            
            if args.export:
                with open(args.export, 'w') as f:
                    json.dump(results, f, indent=2, default=str)
                print(f"Exported to {args.export}\n")
    
    finally:
        recon.close()


if __name__ == '__main__':
    main()
