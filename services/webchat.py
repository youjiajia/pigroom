#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
#   Author  :   jiajia you
#   E-mail  :   hi_youjiajia@163.com
#   Date    :   16/11/21 22:54:18
#   Desc    :
#


import json
import signal

from tornado.gen import engine, Task
from tornado.ioloop import IOLoop
from tornado.web import Application
from tornado.websocket import WebSocketHandler

import tornadoredis

import redis

RedisDB = redis.StrictRedis("127.0.0.1", 6379, 1)

class RoomDemo(WebSocketHandler):
    FINISH_MSG = json.dumps(dict(type='state', data='finish'))

    def initialize(self, **kws):
        self.client = tornadoredis.Client(host=kws["REDIS_HOST"], port=kws["REDIS_PORT"])

    @engine
    def listen(self, channels):
        self.client.connect()
        yield Task(self.client.subscribe, channels)
        self.client.listen(self.on_subscribe)

    def open(self, room_id, *args, **kws):
        self.channels = "room:" + str(room_id)
        self.room_id = room_id
        self.listen(self.channels)
        d = dict(type='message', data="another one come in!!!")
        channel = "room:" + str(self.room_id)
        RedisDB.publish(channel, json.dumps(d))

    def on_message(self, message):
        d = dict(type='message', data=message)
        channel = "room:" + str(self.room_id)
        RedisDB.publish(channel, json.dumps(d))

    def on_subscribe(self, msg):
        if msg.kind == 'message':
            self.write_message(msg.body)
            if "finish" in msg and "state" in msg:
                self.close(1000)
        elif msg.kind == 'disconnect':
            self.close(1011)

    def on_close(self):
        if not self.client.subscribed:
            return
        self.client.unsubscribe(self.channels)
        self.client.disconnect()

    def check_origin(self, origin):
        return True


def init_app(cfg):
    app = Application([
        (r"/pigroom/ws/(\d+)", RoomDemo, cfg),
    ])
    return app


def load_from_obj(objname):
    import config
    obj = getattr(config, objname)
    d = dict()
    for key in dir(obj):
        if key.isupper():
            d[key] = getattr(obj, key)
    return d


def load_config():
    cfg = load_from_obj("DefaultConfig")
    return cfg


def stop():
    IOLoop.current().stop()
    print "server stopped."


def signal_handler(signum, frames):
    IOLoop.current().add_callback_from_signal(stop)


def main(debug=False):
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    cfg = load_config()
    host = cfg.get("SERVER_HOST", '0.0.0.0')
    port = cfg.get("SERVER_PORT", 11000)

    app = init_app(cfg)
    if debug:
        return app

    print "server listen on %s:%d" % (host, port)
    app.listen(port, address=host)

    print "server starts..."
    IOLoop.current().start()


if __name__ == "__main__":
    main()
