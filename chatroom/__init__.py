# -*- coding: utf8 -*-
from bson.objectid import ObjectId
from flask import Flask, request
from flask.json import JSONEncoder

import logging
import os


__all__ = ["app"]

# 通过环境变量来进行配置切换
env = os.environ.get('PIGROOT')
if env not in ['Local']:
    raise EnvironmentError('The environment variable (PIGROOT) is invalid ')


class CustomJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return JSONEncoder.default(self, obj)

app = Flask(__name__)
app.json_encoder = CustomJSONEncoder
app.config.from_object("config.%s" % (env))

async = os.environ.get('WXASYNC')

@app.before_request
def before_request():
    from chatroom.base.xmysql import MYDB
    if async != 'YES':
        MYDB.connect()
    request.authed_user = None


@app.teardown_request
def teardown_request(exception):
    from chatroom.base.xmysql import MYDB
    if not MYDB.is_closed():
        MYDB.close()


@app.after_request

def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE')
    return response


# 日志记录
from wanx.base.log import appHandler
app.logger.setLevel(logging.WARNING)
app.logger.addHandler(appHandler)



