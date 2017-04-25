# -*- coding: utf8 -*-
import settings

import redis


__all__ = ["Redis"]

# api主redis
pool = redis.ConnectionPool(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB
)
Redis = redis.StrictRedis(connection_pool=pool)
