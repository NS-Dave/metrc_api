"""One-off backfill of METRC harvests into Supabase metrc_harvests.

The daily sync dropped every harvest from 2026-02-10 to 2026-10-02 (see
_records in metrc_daily_sync.py). METRC limits lastModified ranges to 24h,
so this walks the range one day at a time.

Usage:
    python backfill_harvests.py --start 2026-02-01 --dry-run
    python backfill_harvests.py --start 2026-02-01
"""
import argparse
from datetime import datetime, timedelta, timezone

from metrc_daily_sync import MetrcSupabaseSync, CULTIVATION_LICENSE


def day_windows(start: datetime, end: datetime):
    """Split [start, end) into consecutive windows of at most 24 hours."""
    out = []
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(hours=24), end)
        out.append((cur, nxt))
        cur = nxt
    return out


def run(start: datetime, dry_run: bool, license_number: str = CULTIVATION_LICENSE):
    s = MetrcSupabaseSync(dry_run=dry_run)
    try:
        s.connect_supabase()
        by_name = {}
        for h in s._records(s.cultivation.get_harvests('active', license_number=license_number)):
            by_name[h.get('Name')] = h
        print(f"active: {len(by_name)}")
        # Metrc reads bare lastModified timestamps as UTC.
        end = datetime.now(timezone.utc).replace(tzinfo=None)
        for w_start, w_end in day_windows(start, end):
            chunk = s._records(s.cultivation.get_harvests(
                'inactive', license_number=license_number,
                last_modified_start=w_start.strftime('%Y-%m-%dT%H:%M:%S'),
                last_modified_end=w_end.strftime('%Y-%m-%dT%H:%M:%S')))
            for h in chunk:
                by_name[h.get('Name')] = h
            if chunk:
                print(f"{w_start:%Y-%m-%d}: {len(chunk)} inactive")
        harvests = list(by_name.values())
        inserted, updated = s.upsert_harvests(harvests, license_number)
        print(f"RESULT pulled={len(harvests)} inserted={inserted} updated={updated} dry_run={dry_run}")
    finally:
        s.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--start", required=True, help="YYYY-MM-DD")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    run(datetime.strptime(a.start, "%Y-%m-%d"), a.dry_run)
