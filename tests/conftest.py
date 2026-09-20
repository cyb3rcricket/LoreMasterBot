"""Pytest configuration loaded before any test file.

A regression test re-runs a past bug to make sure it stays fixed. These
tests must not need a real `.env` file or real Blizzard keys. If those
environment variables are missing, we install fake values so src.config
can import. Environment variables are named settings stored outside the
program; os.environ is the dictionary of those settings for this process.
"""
import os

if not os.environ.get("BLIZZARD_CLIENT_ID"):
    os.environ["BLIZZARD_CLIENT_ID"] = "mock_client_id"
if not os.environ.get("BLIZZARD_CLIENT_SECRET"):
    os.environ["BLIZZARD_CLIENT_SECRET"] = "mock_client_secret"
