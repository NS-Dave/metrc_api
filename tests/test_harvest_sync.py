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


def test_map_harvest_includes_counts_and_packaged_weight():
    out = MetrcSupabaseSync._map_harvest({
        "Id": 5, "Name": "KOKU R9C15 12/22/23", "HarvestType": "Product",
        "CurrentWeight": 100.5, "UnitOfWeightName": "Grams", "IsFinished": False,
        "SourceStrainNames": "Kosher Kush", "DryingLocationName": "Dry Room 3",
        "HarvestStartDate": "2023-12-22", "LastModified": "2023-12-23T01:00:00Z",
        "TotalWasteWeight": 3.0, "TotalWetWeight": 168894.0,
        "PlantCount": 184, "PackageCount": 2, "TotalPackagedWeight": 34000.0,
    })
    assert out["sourcePlantCount"] == 184
    assert out["packageCount"] == 2
    assert out["totalPackagedWeight"] == 34000.0
    assert out["totalWetWeight"] == 168894.0


def test_map_harvest_finished_flag_comes_from_finished_date():
    base = {"Id": 1, "Name": "X"}
    assert MetrcSupabaseSync._map_harvest({**base, "FinishedDate": "2026-01-06"})["isFinished"] is True
    assert MetrcSupabaseSync._map_harvest({**base, "FinishedDate": None})["isFinished"] is False
    assert MetrcSupabaseSync._map_harvest(base)["isFinished"] is False
