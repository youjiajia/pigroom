# -*- coding: utf8 -*-
from wanx import app

import redis


__all__ = ["Redis", "MRedis"]

# api主redis
pool = redis.ConnectionPool(
    host=app.config.get('REDIS_HOST'),
    port=app.config.get('REDIS_PORT'),
    db=0
)
Redis = redis.StrictRedis(connection_pool=pool)

# 消息缓存
mpool = redis.ConnectionPool(
    host=app.config.get('MREDIS_HOST'),
    port=app.config.get('MREDIS_PORT'),
    db=0
)
MRedis = redis.StrictRedis(connection_pool=mpool)
