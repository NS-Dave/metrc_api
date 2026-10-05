#!/usr/bin/env python3
"""
One-time repair for Metrc -> Supabase package gaps found in the 2026-08-24 audit.

Two modes (combinable):

  1. Windowed backfill (default): pulls the ACTIVE and INACTIVE package endpoints
     with explicit lastModifiedStart/End windows (24h chunks) covering
     2026-02-01 -> now for MC281599 and MP281433, and upserts through the
     existing MetrcSupabaseSync machinery. Heals:
       - rows missing entirely (Feb->June dead zone, June startup failures,
         incoming-transfer receipts the implicit default window skipped)
       - rows stuck with stale state/quantity (e.g. the 8/12 MP->MC returns)

  2. Label mode (--labels-file): fetches specific packages one-by-one via
     packages/v2/{label} and upserts them with state derived from
     FinishedDate/ArchivedDate. Used for the 81 archived-in-Metrc packages
     whose archive events predate any lastModified window we pull.

Read-only against Metrc (GETs). Idempotent against Supabase (per-row upserts
keyed on (metrcConnectionId, packageLabel)). Safe to re-run.

Usage:
    python repair_package_gaps.py --dry-run                      # full preview
    python repair_package_gaps.py --dry-run --start 2026-08-10 --end 2026-08-14
    python repair_package_gaps.py --labels-file stale_active_labels.txt --dry-run
    python repair_package_gaps.py                                # real run (COB)
"""

from dotenv import load_dotenv
load_dotenv()

import argparse
import sys
from datetime import datetime, timedelta, timezone

from metrc_daily_sync import MetrcSupabaseSync, CULTIVATION_LICENSE, PROCESSING_LICENSE

CHUNK_HOURS = 24
DEFAULT_START = '2026-02-01'


def parse_day(s: str) -> datetime:
    return datetime.strptime(s, '%Y-%m-%d')


def windowed_backfill(syncer: MetrcSupabaseSync, license_number: str,
                      start: datetime, end: datetime) -> dict:
    """Pull active+inactive endpoints in explicit 24h lastModified windows."""
    totals = {'pulled': 0, 'inserted': 0, 'updated': 0, 'windows': 0, 'errors': 0}
    sync_id = syncer.log_sync_start('packages', license_number, 'repair_backfill', start, end)
    try:
        cur = start
        while cur < end:
            nxt = min(cur + timedelta(hours=CHUNK_HOURS), end)
            s_str = cur.strftime('%Y-%m-%dT%H:%M:%S')
            e_str = nxt.strftime('%Y-%m-%dT%H:%M:%S')
            # Order matters: 'transferred' (membership history -> Inactive) first,
            # then the current-state endpoints, with 'active' LAST so a package
            # that returned to this facility ends the window Active. Chronological
            # windows then guarantee the final state matches the latest event.
            for status in ('transferred', 'inactive', 'active'):
                try:
                    resp = syncer.processing.get_packages(
                        status, license_number=license_number,
                        last_modified_start=s_str, last_modified_end=e_str)
                    rows = resp['Data'] if isinstance(resp, dict) and 'Data' in resp else resp
                    rows = rows or []
                    if rows:
                        ins, upd = syncer.upsert_packages(rows, license_number, status=status)
                        totals['pulled'] += len(rows)
                        totals['inserted'] += ins
                        totals['updated'] += upd
                        print(f"  {license_number} {cur:%Y-%m-%d} {status:8s}: "
                              f"pulled {len(rows):4d}  ins {ins:4d}  upd {upd:4d}", flush=True)
                except Exception as e:
                    totals['errors'] += 1
                    print(f"  [WARN] {license_number} {cur:%Y-%m-%d} {status}: {e}", flush=True)
            totals['windows'] += 1
            cur = nxt
        syncer.log_sync_end(sync_id, totals['pulled'], totals['inserted'],
                            totals['updated'])
    except Exception as e:
        if syncer.conn and not syncer.conn.closed:
            syncer.conn.rollback()
        syncer.log_sync_end(sync_id, totals['pulled'], totals['inserted'],
                            totals['updated'], 'failed', str(e))
        raise
    return totals


def label_repair(syncer: MetrcSupabaseSync, license_number: str, labels: list) -> dict:
    """Fetch specific labels via packages/v2/{label}; state from Finished/ArchivedDate."""
    totals = {'fetched': 0, 'inserted': 0, 'updated': 0, 'not_found': 0}
    sync_id = syncer.log_sync_start('packages', license_number, 'repair_labels')
    try:
        for lab in labels:
            try:
                p = syncer.metrc_client.get(f'packages/v2/{lab}',
                                            license_number=license_number)
                if isinstance(p, dict) and 'Data' in p:
                    p = p['Data']
            except Exception as e:
                totals['not_found'] += 1
                print(f"  [WARN] {lab}: {e}", flush=True)
                continue
            if not p or not p.get('Label'):
                totals['not_found'] += 1
                print(f"  [WARN] {lab}: no payload", flush=True)
                continue
            # Archived or finished packages must not show as Active.
            status = 'inactive' if (p.get('FinishedDate') or p.get('ArchivedDate')) else 'active'
            if not p.get('PackageState'):
                p['PackageState'] = 'Inactive' if status == 'inactive' else 'Active'
            ins, upd = syncer.upsert_packages([p], license_number, status=status)
            totals['fetched'] += 1
            totals['inserted'] += ins
            totals['updated'] += upd
            print(f"  {lab}: {'ins' if ins else 'upd'}  state={p['PackageState']}"
                  f"  qty={p.get('Quantity')}  archived={p.get('ArchivedDate')}"
                  f"  finished={p.get('FinishedDate')}", flush=True)
        syncer.log_sync_end(sync_id, totals['fetched'], totals['inserted'], totals['updated'])
    except Exception as e:
        if syncer.conn and not syncer.conn.closed:
            syncer.conn.rollback()
        syncer.log_sync_end(sync_id, totals['fetched'], totals['inserted'],
                            totals['updated'], 'failed', str(e))
        raise
    return totals


def main():
    ap = argparse.ArgumentParser(description='Repair Metrc->Supabase package gaps (2026-08-24 audit)')
    ap.add_argument('--dry-run', action='store_true',
                    help='Roll back all entity writes (metrc_sync_log rows still persist)')
    ap.add_argument('--start', default=DEFAULT_START, help='Window start day (YYYY-MM-DD)')
    ap.add_argument('--end', default=None, help='Window end day (YYYY-MM-DD), default now')
    ap.add_argument('--license', action='append', dest='licenses',
                    help='Restrict to license(s); default MC281599 + MP281433')
    ap.add_argument('--labels-file', default=None,
                    help='File with one package label per line; runs label mode instead of windows')
    ap.add_argument('--limit', type=int, default=None, help='Per-batch row cap (testing)')
    args = ap.parse_args()

    licenses = args.licenses or [CULTIVATION_LICENSE, PROCESSING_LICENSE]
    start = parse_day(args.start)
    # Metrc reads bare lastModified timestamps as UTC, so "now" must be UTC too.
    end = parse_day(args.end) + timedelta(days=1) if args.end else \
        datetime.now(timezone.utc).replace(tzinfo=None)

    print('=' * 70)
    print('METRC PACKAGE GAP REPAIR' + ('  [DRY RUN — all writes rolled back]' if args.dry_run else ''))
    print(f'Licenses: {licenses}')
    print('=' * 70, flush=True)

    syncer = MetrcSupabaseSync(dry_run=args.dry_run, limit=args.limit)
    grand = {}
    try:
        if args.labels_file:
            labels = [l.strip() for l in open(args.labels_file) if l.strip()]
            # Label mode defaults to the cultivation license only (the 81 stale
            # actives are all MC tags); pass --license to target others.
            if not args.licenses:
                licenses = [CULTIVATION_LICENSE]
            print(f'Label mode: {len(labels)} labels')
            for lic in licenses:
                print(f'\n--- {lic} ---', flush=True)
                grand[lic] = label_repair(syncer, lic, labels)
        else:
            print(f'Windowed backfill: {start:%Y-%m-%d} -> {end:%Y-%m-%d %H:%M} '
                  f'({CHUNK_HOURS}h chunks, active+inactive endpoints)')
            for lic in licenses:
                print(f'\n--- {lic} ---', flush=True)
                grand[lic] = windowed_backfill(syncer, lic, start, end)
    finally:
        syncer.close()

    print('\n' + '=' * 70)
    for lic, t in grand.items():
        print(f'{lic}: {t}')
    if args.dry_run:
        print('DRY RUN: no entity rows were committed.')
    print('=' * 70)
    return 0


if __name__ == '__main__':
    sys.exit(main())
