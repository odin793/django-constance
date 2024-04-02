import time
from typing import Any

from django.utils.functional import LazyObject
from settings import USE_MEMORY_CACHE, MEMORY_CACHE_KEY_TIMEOUT_SECONDS

__version__ = '3.1.0'


class LazyConfig(LazyObject):
    def _setup(self):
        from .base import Config
        self._wrapped = Config()


class ConstanceWithInMemoryCache:
    _OWN_ATTRS = ('_original_config', '_cache', '_cache_timeout_seconds')

    def __init__(self, original_config, timeout_seconds: int):
        self._original_config = original_config
        # Do not use lru cache because we want to manually control particular cache entries
        # to handle cache invalidation on config change (setattr).
        self._cache: dict[str, tuple[Any, float]] = {}
        self._cache_timeout_seconds = timeout_seconds

    def _get_from_cache_or_original(self, attr):
        now = time.time()

        # try from cache first
        if attr in self._cache:
            value, timestamp = self._cache[attr]
            if now - timestamp <= self._cache_timeout_seconds:
                return value

        # read original one if not in cache or if cache is outdated
        value = getattr(self._original_config, attr)
        self._cache[attr] = (value, now)
        return value

    def __getattr__(self, attr):
        # See commends in __setattr__ regarding the routing of attributes
        if attr in ConstanceWithInMemoryCache._OWN_ATTRS:
            return getattr(self, attr)
        elif attr.startswith('_'):
            return getattr(self.__dict__['_original_config'], attr)
        return self._get_from_cache_or_original(attr)

    def __setattr__(self, attr, value):
        if attr in ConstanceWithInMemoryCache._OWN_ATTRS:
            # route our own attributes to our own obj
            super().__setattr__(attr, value)
        elif attr.startswith('_'):
            # route other special attrs to patched config
            setattr(self._original_config, attr, value)
        else:
            # route normal config keys (which are used by app level)
            setattr(self._original_config, attr, value)
            # invalidate cache due to new value of the attribute
            self._cache.pop(attr, None)


if USE_MEMORY_CACHE:
    config = ConstanceWithInMemoryCache(LazyConfig(), timeout_seconds=MEMORY_CACHE_KEY_TIMEOUT_SECONDS)
else:
    config = ConstanceWithInMemoryCache(LazyConfig())