#!/usr/bin/env python3
"""Test sync with pagination enabled."""

from dotenv import load_dotenv
load_dotenv()

from metrc_daily_sync import MetrcSupabaseSync

print("Testing package sync with pagination...")
print("=" * 80)

syncer = MetrcSupabaseSync()
syncer.connect_supabase()

# Sync packages for last 48 hours
syncer.sync_packages_incremental('MC281599', hours=48)

print("=" * 80)
print("Sync complete!")
