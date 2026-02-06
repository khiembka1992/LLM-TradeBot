from dataclasses import dataclass, asdict
from threading import Lock
from typing import Dict, Any


@dataclass
class LLMStats:
    total_requests: int = 0
    total_success: int = 0
    total_errors: int = 0
    last_latency_ms: int = 0
    last_error: str = ""
    last_request_ts: float = 0.0
    last_success_ts: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_lock = Lock()
_stats_by_provider: Dict[str, LLMStats] = {}
_stats_by_model: Dict[str, LLMStats] = {}


def _get_or_create(map_ref: Dict[str, LLMStats], key: str) -> LLMStats:
    stat = map_ref.get(key)
    if stat is None:
        stat = LLMStats()
        map_ref[key] = stat
    return stat


def record_request(provider: str, model: str):
    with _lock:
        for key, store in ((provider, _stats_by_provider), (model, _stats_by_model)):
            stat = _get_or_create(store, key)
            stat.total_requests += 1
            stat.last_request_ts = __import__("time").time()


def record_success(provider: str, model: str, latency_ms: int):
    with _lock:
        for key, store in ((provider, _stats_by_provider), (model, _stats_by_model)):
            stat = _get_or_create(store, key)
            stat.total_success += 1
            stat.last_latency_ms = latency_ms
            stat.last_success_ts = __import__("time").time()
            stat.last_error = ""


def record_error(provider: str, model: str, error: str):
    with _lock:
        for key, store in ((provider, _stats_by_provider), (model, _stats_by_model)):
            stat = _get_or_create(store, key)
            stat.total_errors += 1
            stat.last_error = error


def snapshot() -> Dict[str, Any]:
    with _lock:
        return {
            "providers": {k: v.to_dict() for k, v in _stats_by_provider.items()},
            "models": {k: v.to_dict() for k, v in _stats_by_model.items()},
        }
