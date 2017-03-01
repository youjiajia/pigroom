# -*- coding: utf8 -*-
from wanx import app
from wanx.base.xredis import Redis
from wanx.base.xmongo import DB, client
from wanx.base.xmysql import MYDB
from bson import json_util as bjson

import os
import unittest


class WanxTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Redis.flushall()
        if app.config.get('MONGO_DBNAME') in client.database_names():
            client.drop_database(app.config.get('MONGO_DBNAME'))

        print 'Create database(%s) for unittest ... ok' % (app.config.get('MONGO_DBNAME'))
        kw_path = app.config.get('BASE_DIR') or os.path.abspath(os.path.join(app.root_path, '../'))
        data_path = os.path.join(kw_path, 'wanx/tests/fixtures/')
        for fname in os.listdir(data_path):
            if not fname.startswith('.') and fname.endswith('.json'):
                collection = fname.split('.')[0]
                with open(os.path.join(data_path, fname), 'r') as f:
                    data = f.read()
                    if data:
                        data = bjson.loads(data.strip('\n'))
                        DB.create_collection(collection)
                        DB.get_collection(collection).insert_many(data)

        print 'Create mysql database(%s) for unittest ... ok' % (MYDB.database)
        sql = 'mysql -e "create database if not exists %s  DEFAULT CHARACTER SET utf8 \
               DEFAULT COLLATE utf8_general_ci;"' % (MYDB.database)
        os.popen(sql)
        for fname in os.listdir(data_path):
            if not fname.startswith('.') and fname.endswith('.sql'):
                sql_path = os.path.join(data_path, fname)
                sql = 'mysql %s < %s' % (MYDB.database, sql_path)
                os.popen(sql)

    @classmethod
    def tearDownClass(cls):
        Redis.flushall()
        print 'Drop database(%s) for unittest ... ok' % (app.config.get('MONGO_DBNAME'))
        client.drop_database(app.config.get('MONGO_DBNAME'))
        print 'Drop mysql database(%s) for unittest ... ok' % (MYDB.database)
        sql = 'mysql -e "drop database if exists %s;"' % (MYDB.database)
        os.popen(sql)

    def setUp(self):
        self.app = app.test_client()
