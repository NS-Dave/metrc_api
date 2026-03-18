# Metrc API Directory Cleanup Script
# Removes deprecated, one-time, and obsolete test/debug scripts
# Created: 2026-01-21

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "METRC API DIRECTORY CLEANUP" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Files to delete organized by category
$filesToDelete = @{
    "Superseded Production Scripts" = @(
        "metrc_pull.py",
        "transfer_sync_direction_aware.py"
    )
    
    "One-Time Backfill Scripts (Already Run)" = @(
        "backfill_plants.py",
        "backfill_transfers.py",
        "backfill_transfer_enrichment.py",
        "enrich_historical_packages.py",
        "fill_transfer_deliveries.py",
        "reset_backfill.py"
    )
    
    "Old Migration Scripts (Already Applied)" = @(
        "run_schema_migration.py",
        "run_transferred_migration.py"
    )
    
    "Test Scripts (Exploratory/One-Time)" = @(
        "test_all_transferred.py",
        "test_api_response.py",
        "test_filter_hypothesis.py",
        "test_intransit_endpoint.py",
        "test_intransit_live.py",
        "test_outgoing_deliveries.py",
        "test_package_enrichment.py",
        "test_pagination.py",
        "test_plants_sync.py",
        "test_sync_with_pagination.py",
        "test_transferred_endpoint.py",
        "test_update.py"
    )
    
    "Check/Verify Scripts (One-Time Validation)" = @(
        "check_all_plant_schemas.py",
        "check_delivery_ids.py",
        "check_delivery_structure.py",
        "check_field_coverage.py",
        "check_harvest_schema.py",
        "check_missing_package_status.py",
        "check_new_columns.py",
        "check_packages.py",
        "check_packages_schema.py",
        "check_package_data.py",
        "check_package_status.py",
        "check_plants_data.py",
        "check_plants_schema.py",
        "check_plant_batch_constraints.py",
        "check_sync_logs.py",
        "check_total.py",
        "check_transfer_3133703.py",
        "check_transfer_structure.py",
        "check_update_match.py",
        "check_wholesale_endpoint.py"
    )
    
    "Debug/Analysis Scripts (One-Time)" = @(
        "debug_detailed.py",
        "debug_get_packages.py",
        "debug_pagination.py",
        "debug_request.py",
        "diagnose_package_extraction.py",
        "analyze_json_fields.py",
        "analyze_package_categories.py",
        "analyze_package_categories_v2.py",
        "analyze_package_categories_v3.py",
        "analyze_package_fields.py",
        "analyze_transferred_fallback.py",
        "compare_package_endpoints.py",
        "investigate_active_mismatch.py",
        "final_filter_analysis.py",
        "find_transferred_endpoint.py",
        "show_outgoing_structure.py",
        "show_package_schema.py"
    )
    
    "Verify Scripts (One-Time)" = @(
        "verify_all_statuses.py",
        "verify_new_schema.py",
        "verify_schema.py",
        "verify_supabase_updated.py",
        "validate_all_parsing.py"
    )
    
    "Status Summary Scripts (Should be Markdown)" = @(
        "ENDPOINT_SOURCE_SUMMARY.py",
        "FINAL_STATUS.py",
        "IMPLEMENTATION_COMPLETE.py",
        "QUICK_FIX_SUMMARY.py",
        "SCHEMA_MIGRATION_SUMMARY.py",
        "HISTORY_IMPLEMENTATION_SUMMARY.py",
        "TRANSFERRED_ENDPOINT_STATUS.py",
        "TRANSFER_ENRICHMENT_ANALYSIS.py"
    )
    
    "Obsolete Text Files" = @(
        "backfill_full.txt",
        "backfill_plants_90days.txt",
        "sync_output.txt",
        "sync_test.txt"
    )
}

# Count total files
$totalFiles = 0
foreach ($category in $filesToDelete.Keys) {
    $totalFiles += $filesToDelete[$category].Count
}

Write-Host "This script will delete $totalFiles obsolete files from:" -ForegroundColor Yellow
Write-Host "$scriptDir" -ForegroundColor Yellow
Write-Host ""

# Show what will be deleted
foreach ($category in $filesToDelete.Keys | Sort-Object) {
    Write-Host "[$category]" -ForegroundColor Cyan
    foreach ($file in $filesToDelete[$category] | Sort-Object) {
        $filePath = Join-Path $scriptDir $file
        if (Test-Path $filePath) {
            Write-Host "  OK $file" -ForegroundColor Green
        } else {
            Write-Host "  - $file (not found)" -ForegroundColor DarkGray
        }
    }
    Write-Host ""
}

Write-Host "========================================" -ForegroundColor Yellow
Write-Host ""

# Confirmation
$confirmation = Read-Host "Delete these files? (yes/no)"
if ($confirmation -ne 'yes') {
    Write-Host "Cancelled. No files deleted." -ForegroundColor Yellow
    exit
}

Write-Host ""
Write-Host "Deleting files..." -ForegroundColor Cyan

$deletedCount = 0
$notFoundCount = 0

foreach ($category in $filesToDelete.Keys) {
    foreach ($file in $filesToDelete[$category]) {
        $filePath = Join-Path $scriptDir $file
        if (Test-Path $filePath) {
            try {
                Remove-Item $filePath -Force
                Write-Host "  Deleted: $file" -ForegroundColor Green
                $deletedCount++
            } catch {
                Write-Host "  ERROR deleting $file : $_" -ForegroundColor Red
            }
        } else {
            $notFoundCount++
        }
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "CLEANUP COMPLETE" -ForegroundColor Green
Write-Host "  Deleted: $deletedCount files" -ForegroundColor Green
Write-Host "  Not found: $notFoundCount files" -ForegroundColor DarkGray
Write-Host "========================================" -ForegroundColor Cyan
