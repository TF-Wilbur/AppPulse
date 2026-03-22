"""分析历史存储 — 支持本地 SQLite（默认）和 GCS"""

import hashlib
import json
import os
import sqlite3
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


# ── Storage 接口 ──

class StorageBackend(ABC):
    @abstractmethod
    def load_records(self, user_hash: str) -> list[dict]: ...

    @abstractmethod
    def save_records(self, user_hash: str, records: list[dict]): ...


# ── SQLite 本地存储（默认）──

class LocalStorage(StorageBackend):
    def __init__(self, db_path: str | None = None):
        if db_path is None:
            data_dir = Path.home() / ".review_radar"
            data_dir.mkdir(exist_ok=True)
            db_path = str(data_dir / "history.db")
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_hash TEXT NOT NULL,
                    app_name TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    countries TEXT,
                    platforms TEXT,
                    review_count INTEGER DEFAULT 0,
                    aggregated TEXT,
                    report_text TEXT,
                    analyzed_reviews TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_hash ON analyses(user_hash)")

    def load_records(self, user_hash: str) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM analyses WHERE user_hash = ? ORDER BY timestamp DESC",
                (user_hash,),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def save_records(self, user_hash: str, records: list[dict]):
        """完整替换用户的所有记录（兼容接口）"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM analyses WHERE user_hash = ?", (user_hash,))
            for r in records:
                conn.execute(
                    """INSERT INTO analyses
                       (id, user_hash, app_name, timestamp, countries, platforms,
                        review_count, aggregated, report_text, analyzed_reviews)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        r.get("id"),
                        user_hash,
                        r.get("app_name", ""),
                        r.get("timestamp", time.time()),
                        json.dumps(r.get("countries", []), ensure_ascii=False),
                        json.dumps(r.get("platforms", []), ensure_ascii=False),
                        r.get("review_count", 0),
                        json.dumps(r.get("aggregated"), ensure_ascii=False) if r.get("aggregated") else None,
                        r.get("report_text", ""),
                        json.dumps(r.get("analyzed_reviews"), ensure_ascii=False) if r.get("analyzed_reviews") else None,
                    ),
                )

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        d = dict(row)
        for field in ("countries", "platforms"):
            if d.get(field):
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    d[field] = []
        for field in ("aggregated", "analyzed_reviews"):
            if d.get(field):
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    d[field] = None
        return d


# ── GCS 存储（可选）──

class GCSStorage(StorageBackend):
    _BUCKET_NAME = "review-radar-history"

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            from google.cloud import storage
            self._client = storage.Client()
        return self._client

    def _get_bucket(self):
        return self._get_client().bucket(self._BUCKET_NAME)

    def _blob_path(self, user_hash: str) -> str:
        return f"history/{user_hash}.json"

    def load_records(self, user_hash: str) -> list[dict]:
        bucket = self._get_bucket()
        blob = bucket.blob(self._blob_path(user_hash))
        try:
            data = blob.download_as_text()
            return json.loads(data)
        except Exception:
            return []

    def save_records(self, user_hash: str, records: list[dict]):
        bucket = self._get_bucket()
        blob = bucket.blob(self._blob_path(user_hash))
        blob.upload_from_string(
            json.dumps(records, ensure_ascii=False, indent=2),
            content_type="application/json",
        )


# ── 存储后端选择 ──

_storage: StorageBackend | None = None


def _get_storage() -> StorageBackend:
    global _storage
    if _storage is None:
        backend = os.environ.get("STORAGE_BACKEND", "local").lower()
        if backend == "gcs":
            _storage = GCSStorage()
        else:
            _storage = LocalStorage()
    return _storage


# ── 公共 API（保持向后兼容）──

def user_hash_from_key(api_key: str) -> str:
    """对 API key 做 SHA256 哈希，作为用户标识"""
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


def save_analysis(
    user_hash: str,
    app_name: str,
    countries: list[str],
    platforms: list[str],
    review_count: int,
    aggregated: Optional[dict] = None,
    report: str = "",
    analyzed_reviews: Optional[list[dict]] = None,
) -> int:
    """保存一次分析记录，返回记录 ID"""
    storage = _get_storage()
    records = storage.load_records(user_hash)

    max_id = max((r.get("id", 0) for r in records), default=0)
    new_id = max_id + 1

    records.append({
        "id": new_id,
        "app_name": app_name,
        "timestamp": time.time(),
        "countries": countries,
        "platforms": platforms,
        "review_count": review_count,
        "aggregated": aggregated,
        "report_text": report,
        "analyzed_reviews": analyzed_reviews,
    })

    # 只保留最近 50 条
    records = records[-50:]

    storage.save_records(user_hash, records)
    return new_id


def list_analyses(user_hash: str, limit: int = 20) -> list[dict]:
    """列出用户的分析历史"""
    storage = _get_storage()
    records = storage.load_records(user_hash)
    records.sort(key=lambda r: r.get("timestamp", 0), reverse=True)
    result = []
    for r in records[:limit]:
        result.append({
            "id": r["id"],
            "app_name": r.get("app_name", ""),
            "timestamp": r.get("timestamp", 0),
            "countries": r.get("countries", []),
            "platforms": r.get("platforms", []),
            "review_count": r.get("review_count", 0),
        })
    return result


def get_analysis(user_hash: str, analysis_id: int) -> Optional[dict]:
    """获取单条分析记录（含完整数据）"""
    storage = _get_storage()
    records = storage.load_records(user_hash)
    for r in records:
        if r.get("id") == analysis_id:
            return r
    return None


def delete_analysis(user_hash: str, analysis_id: int) -> bool:
    """删除一条分析记录"""
    storage = _get_storage()
    records = storage.load_records(user_hash)
    new_records = [r for r in records if r.get("id") != analysis_id]
    if len(new_records) == len(records):
        return False
    storage.save_records(user_hash, new_records)
    return True
