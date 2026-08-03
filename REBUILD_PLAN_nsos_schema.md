# METRC Python Pipeline — Rebuild to NSOS Schema

**Date:** 2026-06-29
**Goal:** Restore daily METRC cultivation/processing sync by rewriting `metrc_daily_sync.py`
upserts to the NativeSunOperatingSystem (NSOS) camelCase, connection-scoped schema now
present in the shared `ns-ops` Supabase project (`kacquxbizuqgsslnubdy`).

## Context
- Legacy Python wrote snake_case (`label`, `license_number`, metrc id as PK `id`).
- NSOS schema: camelCase columns; `id` is a generated uuid; metrc id lives in
  `metrc<Entity>Id` (integer); every row scoped by `metrcConnectionId` (uuid).
- Natural upsert key = (`metrcConnectionId`, `metrc<Entity>Id`).
- NSOS sync engine exists but is OFF (0 API calls); dual-writer risk accepted.

## License → connection map (from `metrc_connections`)
| Const | License | metrcConnectionId |
|-------|---------|-------------------|
| CULTIVATION_LICENSE | MC281599 | 288547c9-798b-4f93-83bc-543f31544608 |
| PROCESSING_LICENSE  | MP281433 | 9dc22070-b67b-4fe5-87c6-199693be723a |

Resolve at runtime: `SELECT id FROM metrc_connections WHERE "licenseNumber"=%s` (don't hardcode).

## Target schemas (entity → key columns)
- **metrc_packages**: metrcPackageId, packageLabel, packageType, packageState, itemName,
  itemCategory, productCategoryName, quantity, unitOfMeasure, initialQuantity, locationName,
  packagedDate, receivedDate, finishedDate, lastModifiedAt, sourceHarvestNames[],
  sourcePackageLabels[], labTestingState, isTestingSample, isTradeSample, unitCostPrice,
  totalCost, note, isOnHold, isProductionBatch, productionBatchNumber, isDonation,
  donatedDate, lastSyncedAt
- **metrc_harvests**: metrcHarvestId, harvestName, harvestType, currentWeight, unitOfWeight,
  isFinished, strainName, dryingLocationName, harvestStartDate, finishedDate, lastModifiedAt,
  sourcePlantCount, sourcePlantLabels[], totalWasteWeight, totalWetWeight,
  totalRestorativeWasteWeight, packageCount, lastSyncedAt
- **metrc_plants**: metrcPlantId, plantLabel, plantState, growthPhase, strainName,
  locationName, plantedDate, vegetativeDate, floweringDate, harvestedDate, destroyedDate,
  lastModifiedAt, plantBatchName, plantBatchType, isOnHold, lastSyncedAt
- **metrc_plant_batches**: metrcBatchId, batchName, batchType, count, initialCount,
  trackedCount, untrackedCount, packagedCount, destroyedCount, strainName, locationName,
  plantedDate, lastModifiedAt, sourcePackageLabel, lastSyncedAt
- **metrc_transfers**: metrcTransferId, manifestNumber, transferType, shipmentTypeName,
  shipper*/destination*/transporter* facility fields, driverName, driverLicenseNumber,
  vehicle*, transferState, createdDate, shippedDate, estimated*/receivedDate, lastModifiedAt,
  packageCount, shipmentNote, isOnHold, containsPlantPackage, containsProductPackage, lastSyncedAt
- **metrc_transfer_packages**: survived (verify columns before writing).
- **metrc_transfer_transporters**: DROPPED → disable `upsert_transfer_transporters` +
  the transporter-detail enrichment path; log a one-line notice instead.

NOT-NULL columns needing values on insert: `metrcConnectionId`, the entity name field
(e.g. harvestName/plantLabel/packageLabel/batchName/manifestNumber), `unitOfWeight`(harvests),
`count`(batches), boolean flags (isFinished/isOnHold/contains*), and `lastSyncedAt`,
`createdAt`, `updatedAt` (set to now()).

## Implementation steps
1. Add `resolve_connection_id(license_number)` (cached dict) on the syncer.
2. Replace each `upsert_*`:
   - Existence check: `SELECT id FROM <tbl> WHERE "metrcConnectionId"=%s AND "metric<Entity>Id"=%s`.
   - INSERT lets `id` default (gen_random_uuid); set createdAt/updatedAt/lastSyncedAt=now().
   - UPDATE sets mapped camelCase columns + updatedAt/lastSyncedAt=now() on match.
   - Quote every camelCase identifier ("packageLabel" etc.).
3. Map METRC API response fields → new columns (API field names unchanged; only DB target changes).
4. Disable transporter enrichment + `upsert_transfer_transporters` (table gone).
5. Keep `metrc_sync_log` writes (table restored, legacy schema) for run auditing.
6. Add `--dry-run` (rollback at end) and `--limit N` flags for safe testing.

## Verification
1. `--dry-run` single license: confirm row counts + 0 errors, transaction rolled back.
2. Live run scoped to MC281599 only; verify new rows carry correct metrcConnectionId and
   that updatedAt advances past the frozen 2026-02-10 timestamp on touched rows.
3. Full run (both licenses); confirm exit code 0 and metrc_sync_log entries 'completed'.
4. Re-enable / confirm the daily scheduled task.

## Rollback
All writes are upserts scoped to the two 140 connections; no destructive ops. If NSOS
worker is later enabled, revisit to avoid schedule overlap (Python 6AM vs NSOS 15-min).
