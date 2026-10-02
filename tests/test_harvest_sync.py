import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from metrc_daily_sync import MetrcSupabaseSync


def test_records_accepts_list():
    assert MetrcSupabaseSync._records([{"Id": 1}, {"Id": 2}]) == [{"Id": 1}, {"Id": 2}]


def test_records_accepts_wrapped_dict():
    assert MetrcSupabaseSync._records({"Data": [{"Id": 1}]}) == [{"Id": 1}]


def test_records_returns_empty_for_none_and_unknown():
    assert MetrcSupabaseSync._records(None) == []
    assert MetrcSupabaseSync._records({"Message": "nope"}) == []
    assert MetrcSupabaseSync._records({"Data": None}) == []


class _FakeCultivation:
    def __init__(self):
        self.calls = []

    def get_harvests(self, status, license_number=None,
                     last_modified_start=None, last_modified_end=None):
        self.calls.append(status)
        if status == "active":
            return [{"Id": 10, "Name": "ACTIVE-1"}]          # list, as the paginator returns
        return {"Data": [{"Id": 20, "Name": "INACTIVE-1"}]}  # wrapped, legacy shape


def test_sync_harvests_passes_list_responses_to_upsert():
    s = object.__new__(MetrcSupabaseSync)          # skip __init__ (no API/DB needed)
    s.cultivation = _FakeCultivation()
    s.conn = None
    captured = {}
    s.log_sync_start = lambda *a, **k: 1
    s.log_sync_end = lambda sync_id, pulled, ins, upd, *a, **k: captured.update(pulled=pulled)
    s.upsert_harvests = lambda harvests, lic: (captured.update(names=[h["Name"] for h in harvests]) or (len(harvests), 0))

    s.sync_harvests_incremental("MC281599", hours=24)

    assert captured["names"][0] == "ACTIVE-1"
    assert "INACTIVE-1" in captured["names"]
    assert captured["pulled"] == len(captured["names"]) >= 2
