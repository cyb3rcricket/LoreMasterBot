"""Pytest configuration and session-wide fixtures for LoreMasterBot."""
import os

if not os.environ.get("BLIZZARD_CLIENT_ID"):
    os.environ["BLIZZARD_CLIENT_ID"] = "mock_client_id"
if not os.environ.get("BLIZZARD_CLIENT_SECRET"):
    os.environ["BLIZZARD_CLIENT_SECRET"] = "mock_client_secret"
