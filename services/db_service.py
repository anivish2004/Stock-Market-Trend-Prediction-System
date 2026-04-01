from __future__ import annotations

from datetime import datetime
from typing import Any

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import PyMongoError


class MongoService:
    def __init__(self, mongo_uri: str, database_name: str) -> None:
        self.available = True
        self.error_message = ""
        try:
            self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=12000, connectTimeoutMS=12000)
            self.client.admin.command("ping")
            self.database = self.client[database_name]
            self.collection: Collection = self.database["predictions"]
        except PyMongoError as error:
            self.available = False
            self.error_message = str(error)
            self.client = None
            self.database = None
            self.collection = None

    def store_prediction(self, payload: dict[str, Any]) -> None:
        if not self.available or self.collection is None:
            return
        self.collection.insert_one(payload)

    def fetch_recent_predictions(self, limit: int = 10) -> list[dict[str, Any]]:
        if not self.available or self.collection is None:
            return []
        records = list(self.collection.find({}, {"_id": 0}).sort("created_at", -1).limit(limit))
        return self._format_records(records)

    def search_predictions(
        self,
        symbol: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if not self.available or self.collection is None:
            return []

        query: dict[str, Any] = {}
        if symbol:
            query["symbol"] = symbol.upper()
        if start_date or end_date:
            created_at_filter: dict[str, Any] = {}
            if start_date:
                created_at_filter["$gte"] = start_date
            if end_date:
                created_at_filter["$lte"] = end_date
            query["created_at"] = created_at_filter

        records = list(self.collection.find(query, {"_id": 0}).sort("created_at", -1).limit(limit))
        return self._format_records(records)

    @staticmethod
    def _format_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for record in records:
            if "bullish_probability" in record:
                record["bullish_probability"] = f"{record['bullish_probability'] * 100:.2f}%"
            if "validation_accuracy" in record:
                record["validation_accuracy"] = f"{record['validation_accuracy'] * 100:.2f}%"
            if "precision" in record:
                record["precision"] = f"{record['precision'] * 100:.2f}%"
            if "recall" in record:
                record["recall"] = f"{record['recall'] * 100:.2f}%"
            if "f1_score" in record:
                record["f1_score"] = f"{record['f1_score'] * 100:.2f}%"
        return records
