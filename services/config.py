from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> None:
        return None


load_dotenv()


@dataclass(slots=True)
class AppConfig:
    mongo_uri: str = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    database_name: str = os.getenv("MONGO_DB_NAME", "quantumvest_ai")
