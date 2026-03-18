"""
Package history tracking helper functions.

Captures package state changes to metrc_packages_history table.
"""
import json
from typing import Dict, List, Optional
from datetime import datetime
import psycopg2


def detect_changes(old_data: Dict, new_data: Dict, important_fields: List[str]) -> tuple:
    """
    Detect which fields changed between old and new package data.
    
    Args:
        old_data: Previous package state
        new_data: New package state
        important_fields: List of field names to check for changes
        
    Returns:
        (change_type, changed_fields_list)
    """
    if not old_data:
        return ('created', [])
    
    changed_fields = []
    state_changed = False
    quantity_changed = False
    
    for field in important_fields:
        old_val = old_data.get(field)
        new_val = new_data.get(field)
        
        if old_val != new_val:
            changed_fields.append(field)
            
            # Track significant changes
            if field in ('is_finished', 'is_archived', 'is_on_hold', 'finished_date', 'archived_date'):
                state_changed = True
            elif field == 'quantity':
                quantity_changed = True
    
    # Determine change type
    if not changed_fields:
        return ('no_change', [])
    elif state_changed:
        return ('state_change', changed_fields)
    elif quantity_changed:
        return ('quantity_change', changed_fields)
    else:
        return ('updated', changed_fields)


def capture_history_before_update(cursor, package_label: str, new_data: Dict, sync_time: datetime) -> None:
    """
    Before updating a package, capture its current state to history.
    
    Args:
        cursor: Database cursor
        package_label: Package label
        new_data: New package data (to detect changes)
        sync_time: Current sync timestamp
    """
    # Fetch current state
    cursor.execute("""
        SELECT 
            id, label, license_number, package_type, product_name, product_category_name,
            item_name, item_id, quantity, unit_of_measure, packaged_date,
            initial_lab_testing_state, lab_testing_state, lab_testing_state_date,
            is_production_batch, production_batch_number, source_production_batch_numbers,
            source_package_labels, source_harvest_names, is_trade_sample, is_testing_sample,
            is_process_validation_test_sample, is_donation, is_on_hold, archived_date,
            finished_date, location_name, note, last_modified,
            is_finished, is_archived, endpoint_source, data, synced_at
        FROM metrc_packages
        WHERE label = %s
    """, (package_label,))
    
    current = cursor.fetchone()
    if not current:
        return  # Package doesn't exist yet, no history to capture
    
    # Unpack current state
    (pkg_id, label, license, pkg_type, prod_name, prod_cat, item_name, item_id,
     quantity, unit, packaged_date, init_lab, lab_state, lab_state_date,
     is_prod_batch, prod_batch_num, src_prod_batch, src_pkg_labels, src_harvest,
     is_trade, is_test, is_val_test, is_donation, is_hold, arch_date, fin_date,
     location, note, last_mod, is_fin, is_arch, endpoint, data_json, synced_at) = current
    
    # Parse old data for comparison
    old_data = {
        'quantity': quantity,
        'is_finished': is_fin,
        'is_archived': is_arch,
        'is_on_hold': is_hold,
        'finished_date': str(fin_date) if fin_date else None,
        'archived_date': str(arch_date) if arch_date else None,
        'location_name': location,
        'endpoint_source': endpoint
    }
    
    # Detect what changed
    important_fields = ['quantity', 'is_finished', 'is_archived', 'is_on_hold', 
                       'finished_date', 'archived_date', 'location_name', 'endpoint_source']
    change_type, changed_fields = detect_changes(old_data, new_data, important_fields)
    
    # Only capture history if something actually changed
    if change_type == 'no_change':
        return
    
    # Mark previous "current" record as no longer current
    cursor.execute("""
        UPDATE metrc_packages_history
        SET is_current = false,
            valid_to = %s
        WHERE label = %s
          AND is_current = true
    """, (sync_time, package_label))
    
    # Insert current state into history
    cursor.execute("""
        INSERT INTO metrc_packages_history (
            id, label, license_number, valid_from, valid_to, is_current,
            change_type, changed_fields,
            package_type, product_name, product_category_name, item_name, item_id,
            quantity, unit_of_measure, packaged_date,
            initial_lab_testing_state, lab_testing_state, lab_testing_state_date,
            is_production_batch, production_batch_number, source_production_batch_numbers,
            source_package_labels, source_harvest_names,
            is_trade_sample, is_testing_sample, is_process_validation_test_sample,
            is_donation, is_on_hold, archived_date, finished_date,
            location_name, note, last_modified,
            is_finished, is_archived, endpoint_source,
            data, synced_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s
        )
    """, (
        pkg_id, label, license, synced_at, sync_time, False,
        change_type, json.dumps(changed_fields),
        pkg_type, prod_name, prod_cat, item_name, item_id,
        quantity, unit, packaged_date,
        init_lab, lab_state, lab_state_date,
        is_prod_batch, prod_batch_num, src_prod_batch,
        src_pkg_labels, src_harvest,
        is_trade, is_test, is_val_test,
        is_donation, is_hold, arch_date, fin_date,
        location, note, last_mod,
        is_fin, is_arch, endpoint,
        json.dumps(data_json) if isinstance(data_json, dict) else data_json, synced_at
    ))


def create_initial_history_entry(cursor, package_data: Dict, sync_time: datetime) -> None:
    """
    Create initial history entry for a newly created package.
    
    Args:
        cursor: Database cursor
        package_data: Package data dictionary (same as used for insert)
        sync_time: Current sync timestamp
    """
    cursor.execute("""
        INSERT INTO metrc_packages_history (
            id, label, license_number, valid_from, valid_to, is_current,
            change_type,
            package_type, product_name, product_category_name, item_name, item_id,
            quantity, unit_of_measure, packaged_date,
            initial_lab_testing_state, lab_testing_state, lab_testing_state_date,
            is_production_batch, production_batch_number, source_production_batch_numbers,
            source_package_labels, source_harvest_names,
            is_trade_sample, is_testing_sample, is_process_validation_test_sample,
            is_donation, is_on_hold, archived_date, finished_date,
            location_name, note, last_modified,
            is_finished, is_archived, endpoint_source,
            data, synced_at
        ) VALUES (
            %(id)s, %(label)s, %(license_number)s, %(synced_at)s, NULL, true,
            'created',
            %(package_type)s, %(product_name)s, %(product_category_name)s, %(item_name)s, %(item_id)s,
            %(quantity)s, %(unit_of_measure)s, %(packaged_date)s,
            %(initial_lab_testing_state)s, %(lab_testing_state)s, %(lab_testing_state_date)s,
            %(is_production_batch)s, %(production_batch_number)s, %(source_production_batch_numbers)s,
            %(source_package_labels)s, %(source_harvest_names)s,
            %(is_trade_sample)s, %(is_testing_sample)s, %(is_process_validation_test_sample)s,
            %(is_donation)s, %(is_on_hold)s, %(archived_date)s, %(finished_date)s,
            %(location_name)s, %(note)s, %(last_modified)s,
            %(is_finished)s, %(is_archived)s, %(endpoint_source)s,
            %(data)s, %(synced_at)s
        )
    """, package_data)
