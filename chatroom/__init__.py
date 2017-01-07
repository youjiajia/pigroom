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
    from wanx.base.xmysql import MYDB
    if async != 'YES':
        MYDB.connect()
    request.authed_user = None


@app.teardown_request
def teardown_request(exception):
    from wanx.base.xmysql import MYDB
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


if async == 'YES':
    import wanx.views.async
else:
    import wanx.views.comment
    import wanx.views.game
    import wanx.views.user
    import wanx.views.video
    import wanx.views.home
    import wanx.views.upload
    import wanx.views.migu
    import wanx.views.msg
    import wanx.views.traffic
    import wanx.views.xlive
    import wanx.views.datang
    import wanx.views.task
    import wanx.views.credit
    import wanx.views.gift
    import wanx.views.store

    from wanx.share.share import share
    app.register_blueprint(share)

    from wanx.views.activity.comment import comment
    from wanx.views.activity.video import video
    from wanx.views.activity.activity import activity
    from wanx.views.activity.live import live
    app.register_blueprint(comment)
    app.register_blueprint(activity)
    app.register_blueprint(video)
    app.register_blueprint(live)
