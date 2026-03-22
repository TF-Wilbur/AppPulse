"""LLM 供应商预设配置"""

PROVIDERS: dict[str, dict] = {
    "OpenAI": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
        "known_models": [
            "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4",
            "gpt-3.5-turbo", "o1", "o1-mini", "o3-mini",
        ],
    },
    "MiniMax": {
        "base_url": "https://api.minimax.chat/v1",
        "default_model": "MiniMax-M2.7",
        "known_models": [
            "MiniMax-M2.7", "MiniMax-M2.7-highspeed",
            "MiniMax-M2.5", "MiniMax-M2.5-highspeed",
            "MiniMax-M2.1", "MiniMax-M2.1-highspeed",
            "MiniMax-M2",
            "MiniMax-Text-01", "MiniMax-Text-01-128k",
        ],
    },
    "智谱 GLM": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
        "known_models": [
            "glm-4-flash", "glm-4-plus", "glm-4-air", "glm-4",
            "glm-4-long", "glm-3-turbo",
        ],
    },
    "Kimi (Moonshot)": {
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
        "known_models": [
            "moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k",
        ],
    },
    "自定义": {
        "base_url": "",
        "default_model": "",
        "known_models": [],
    },
}


def list_provider_names() -> list[str]:
    """返回所有供应商名称"""
    return list(PROVIDERS.keys())


def get_provider(name: str) -> dict:
    """获取供应商配置"""
    return PROVIDERS.get(name, PROVIDERS["自定义"])


def fetch_models(api_key: str, base_url: str) -> tuple[list[str], str]:
    """先尝试 GET /models 接口，失败则回退到预设模型列表"""
    import httpx

    url = f"{base_url.rstrip('/')}/models"
    try:
        resp = httpx.get(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            models_raw = data.get("data", data) if isinstance(data, dict) else data
            if isinstance(models_raw, list):
                ids = sorted([
                    m.get("id", "") if isinstance(m, dict) else str(m)
                    for m in models_raw
                    if (m.get("id") if isinstance(m, dict) else m)
                ])
                if ids:
                    return ids, ""
    except Exception:
        pass

    # 回退：根据 base_url 匹配预设模型
    for cfg in PROVIDERS.values():
        if cfg["base_url"] and cfg["base_url"].rstrip("/") == base_url.rstrip("/"):
            if cfg.get("known_models"):
                return cfg["known_models"], ""
    return [], "该供应商不支持模型列表接口，请手动输入模型名称"
