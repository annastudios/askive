"""
Key-value store for caching and chat memory.

With REDIS_URL set (docker-compose, Kubernetes) everything lives in
Redis, so all API replicas share one cache and conversation memory
survives restarts. Without it (local dev, tests) a small in-process
store with the same interface is used instead.

Only the handful of Redis commands the app needs are implemented by
the fallback: get, set (with expiry), incr, rpush, ltrim, lrange,
expire, ping.
"""

import threading
import time

import redis

from app.config import REDIS_URL


class InMemoryStore:
    def __init__(self):
        self._data: dict[str, object] = {}
        self._expires: dict[str, float] = {}
        self._lock = threading.Lock()

    def _alive(self, key: str) -> bool:
        expiry = self._expires.get(key)
        if expiry is not None and expiry <= time.monotonic():
            self._data.pop(key, None)
            self._expires.pop(key, None)
        return key in self._data

    def ping(self) -> bool:
        return True

    def get(self, key: str) -> str | None:
        with self._lock:
            return self._data[key] if self._alive(key) else None

    def set(self, key: str, value: str, ex: int | None = None):
        with self._lock:
            self._data[key] = value
            if ex is None:
                self._expires.pop(key, None)
            else:
                self._expires[key] = time.monotonic() + ex

    def incr(self, key: str) -> int:
        with self._lock:
            value = int(self._data[key]) + 1 if self._alive(key) else 1
            self._data[key] = str(value)
            return value

    def expire(self, key: str, seconds: int):
        with self._lock:
            if self._alive(key):
                self._expires[key] = time.monotonic() + seconds

    def rpush(self, key: str, value: str):
        with self._lock:
            if not self._alive(key):
                self._data[key] = []
            self._data[key].append(value)

    def lrange(self, key: str, start: int, end: int) -> list[str]:
        with self._lock:
            if not self._alive(key):
                return []
            items = self._data[key]
            # Redis ranges are inclusive and -1 means "last element".
            stop = None if end == -1 else end + 1
            return list(items[start:stop])

    def ltrim(self, key: str, start: int, end: int):
        with self._lock:
            if self._alive(key):
                stop = None if end == -1 else end + 1
                self._data[key] = self._data[key][start:stop]


def _connect():
    if REDIS_URL:
        return redis.Redis.from_url(REDIS_URL, decode_responses=True)
    return InMemoryStore()


store = _connect()
