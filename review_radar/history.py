"""分析历史存储 — GCS JSON"""

import hashlib
import json
import time
from typing import Optional

_BUCKET_NAME = "review-radar-history"
_client = None


def _get_client():
    global _client
    if _client is None:
        from google.cloud import storage
        _client = storage.Client()
    return _client


def _get_bucket():
    return _get_client().bucket(_BUCKET_NAME)


def _blob_path(user_hash: str) -> str:
    """每个用户一个 JSON 文件"""
    return f"history/{user_hash}.json"


def _load_user_data(user_hash: str) -> list[dict]:
    """从 GCS 加载用户的历史记录"""
    bucket = _get_bucket()
    blob = bucket.blob(_blob_path(user_hash))
    try:
        data = blob.download_as_text()
        return json.loads(data)
    except Exception:
        return []


def _save_user_data(user_hash: str, records: list[dict]):
    """保存用户的历史记录到 GCS"""
    bucket = _get_bucket()
    blob = bucket.blob(_blob_path(user_hash))
    blob.upload_from_string(
        json.dumps(records, ensure_ascii=False, indent=2),
        content_type="application/json",
    )


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
) -> int:
    """保存一次分析记录，返回记录 ID"""
    records = _load_user_data(user_hash)

    # 生成自增 ID
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
    })

    # 只保留最近 50 条
    records = records[-50:]

    _save_user_data(user_hash, records)
    return new_id


def list_analyses(user_hash: str, limit: int = 20) -> list[dict]:
    """列出用户的分析历史"""
    records = _load_user_data(user_hash)
    # 按时间倒序，返回摘要信息
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
    records = _load_user_data(user_hash)
    for r in records:
        if r.get("id") == analysis_id:
            return r
    return None


def delete_analysis(user_hash: str, analysis_id: int) -> bool:
    """删除一条分析记录"""
    records = _load_user_data(user_hash)
    new_records = [r for r in records if r.get("id") != analysis_id]
    if len(new_records) == len(records):
        return False
    _save_user_data(user_hash, new_records)
    return True
