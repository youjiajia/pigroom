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



# 日志记录
from wanx.base.log import appHandler
app.logger.setLevel(logging.WARNING)
app.logger.addHandler(appHandler)



