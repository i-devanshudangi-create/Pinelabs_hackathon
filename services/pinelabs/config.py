from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

PINE_LABS_BASE_URL = os.getenv("PINE_LABS_BASE_URL", "https://pluraluat.v2.pinepg.in/api")
PINE_LABS_CLIENT_ID = os.getenv("PINE_LABS_CLIENT_ID", "")
PINE_LABS_CLIENT_SECRET = os.getenv("PINE_LABS_CLIENT_SECRET", "")
PINE_LABS_MID = os.getenv("PINE_LABS_MID", "")
