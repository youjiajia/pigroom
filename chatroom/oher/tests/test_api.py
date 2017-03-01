# -*- coding: utf8 -*-
from flask import json
from urlparse import urljoin
from wanx import app
from . import WanxTestCase
from hashlib import md5

import random
import os
import time


class ApiTestCase(WanxTestCase):
    """
    api测试用例
    """
    USER_ID = '56246d292d7fa20787d683b4'
    TARGET_USER_ID = '55efe64feb43a14b0fcff4e6'
    GAME_ID = '55efe64deb43a14b0fcff4e1'
    VIDEO_ID = '55efe87aeb43a14de2d05fd2'
    COMMENT_ID = '55efe889eb43a14de2d0618b'
    MIGU_VIDEO_ID = '55efe87aeb43a14de2d05fd3'  # 为了不影响comment相关，migu单独一个video_id
    UT = ''
    TARGET_UT = ''
    xml = '''<?xml version="1.0" encoding="utf-8"?>
                <REQUEST>
                    <RequestID>201507291527001</RequestID>
                    <ACTION>MeberShipMessage</ACTION>
                    <BODY>
                        <Member>
                            <Mobile>13612859652</Mobile>
                            <CRMApplyCode>10001</CRMApplyCode>
                            <ResultCode>0</ResultCode>
                            <ResultMsg>成功</ResultMsg>
                        </Member>
                        <OrdNum>20150729152217</OrdNum>
                    </BODY>
                </REQUEST>
        '''

    VIDEO_RETURN_KEYS = [u'video_id', u'ratio', u'author', u'is_favored', u'is_liked',
                         u'tags', u'cover', u'comment_count', u'share_url', u'create_at',
                         u'url', u'game', u'like_count', u'vv', u'duration', u'title',
                         u'status', u'is_online', u'gift_count', u'gift_num', u'event_id',
                         u'share_title']

    GAME_RETURN_KEYS = [u'subscription_count', u'video_count', u'description', u'subscribed',
                        u'tags', u'url', u'bid', u'cover', u'create_at', u'big_icon', u'name',
                        u'package_size', u'package_id', u'popular_count', u'game_id', u'icon',
                        u'package_version', u'developer', u'contain_sdk', u'status', u'share_url',
                        u'is_download', u'is_subscribe', u'is_online', u'package_segment',
                        u'slogan', u'intro', u'url_ios', u'is_download_ios', u'is_subscribe_ios',
                        u'share_title', u'share_summary', u'on_assistant', u'is_live_label']

    USER_RETURN_KEYS = [u'is_followed', u'video_count', u'user_id', u'name', u'following_count',
                        u'subscriptions', u'gender', u'favor_count', u'binding', u'phone',
                        u'birthday', u'register_at', u'photo', u'follower_count', u'logo',
                        u'nickname', u'email', u'signature', u'migu_id', u'announcement',
                        u'status', u'bans', u'is_match']

    GAME_HOME_RETURN_KEYS = [u'modules', u'mainstays', u'hot_games', u'ads', u'grids']

    ACTIVITY_ID = '56f1119f421aa983702175d6'
    ACTIVITY_COMMENT_ID = '57031f49421aa94caf764eaf'

    def setUp(self):
        super(ApiTestCase, self).setUp()

        _data = dict(name='dongin', password='abcd1234')
        resp = self.app.post('/users/login', data=_data)
        self.assertEqual(resp.status_code, 200, 'user login error')
        self.assertEqual(json.loads(resp.data)['status'], 0)
        self.UT = json.loads(resp.data)['data']['ut']

        _data = dict(name='io123456', password='abcd1234')
        resp = self.app.post('/users/login', data=_data)
        self.assertEqual(resp.status_code, 200, 'user login error')
        self.assertEqual(json.loads(resp.data)['status'], 0)
        self.TARGET_UT = json.loads(resp.data)['data']['ut']

        # 测试提前伪造直播数据
        from wanx.base.xredis import Redis
        from wanx.platforms.xlive import Xlive
        key = 'config:live_api_url'
        Redis.set(key, 'http://live-stream.molizhen.com/events')
        kw_path = app.config.get('BASE_DIR') or os.path.abspath(os.path.join(app.root_path, '../'))
        data_file = os.path.join(kw_path, 'wanx/tests/fixtures/lives.data')
        with open(data_file, 'r') as f:
            data = f.read()
            data = json.loads(data.strip('\n'))
            Redis.setex(Xlive.ALL_LIVES, 60, json.dumps(data))

    def test_home(self):
        resp = self.app.get('/daily_visit?device=111111&ut=%s' % self.UT)
        self.assertEqual(resp.status_code, 200, 'daily visit error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        resp = self.app.get('/app_in_review?version=3.1.2')
        self.assertEqual(resp.status_code, 200, 'app in review error')
        self.assertTrue(json.loads(resp.data)['data']['in_review'])

        resp = self.app.get('/app_in_review?version=3.1.1')
        self.assertEqual(resp.status_code, 200, 'app in review error')
        self.assertFalse(json.loads(resp.data)['data']['in_review'])

        resp = self.app.get('/launch_ads')
        self.assertEqual(resp.status_code, 200, 'get launch ads error')
        rv = json.loads(resp.data)
        self.assertTrue(rv["data"]["ad"]['ad_id'] in ['560167fc6e9552296b893ffb',
                                                      '560168646e9552298ca86698'])
        self.assertEqual(rv['status'], 0)

        resp = self.app.get('/home?os=ios&version_code=1')
        self.assertEqual(resp.status_code, 200, 'get home page error')
        rv = json.loads(resp.data)
        self.assertEquals(len(rv["data"]["banners"]), 1, "banner num error!")
        self.assertEqual(rv['status'], 0)

        resp = self.app.get('/banners?os=ios&version_code=1')
        self.assertEqual(resp.status_code, 200, 'get banner error')
        rv = json.loads(resp.data)
        # 返回的banner数跟设置相同，包括顺序
        self.assertEqual(len(rv["data"]["banners"]), 1, "banner num error!")
        self.assertEqual(rv["data"]["banners"][0]["banner_id"],
                         "560168646e9552298ca86698", "banner seq error!")
        self.assertEqual(rv['status'], 0)

        resp = self.app.get('/banners/sdk')
        self.assertEqual(resp.status_code, 200, 'get sdk banner error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        resp = self.app.get('/search?type=all&keyword=对面')
        self.assertEqual(resp.status_code, 200, 'get banner error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        resp = self.app.get('/fixed_banners?os=android&version_code=1')
        self.assertEqual(resp.status_code, 200, 'get fixed banner error')
        rv = json.loads(resp.data)
        # 返回的banner数跟设置相同
        self.assertEqual(len(rv["data"]["banners"]), 2, "banner num error!")
        positions = [rv["data"]["banners"][0]["position"],rv["data"]["banners"][1]["position"]]
        self.assertEqual(sorted(positions),[1,2], "banner position error!")
        self.assertEqual(rv['status'], 0)

    def test_comment(self):
        _data = dict(video_id=self.VIDEO_ID, content='习近平', ut=self.UT)
        resp = self.app.post('/user/opt/submit-comment', data=_data)
        rv = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200, 'create comment error')
        self.assertEqual(rv['status'], -10003)

        _data = dict(video_id=self.VIDEO_ID, content='不错', ut=self.UT)
        resp = self.app.post('/user/opt/submit-comment', data=_data)
        rv = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200, 'create comment error')
        self.assertEqual(rv['status'], 0)
        # 检查发表评论和返回评论是否一致
        self.assertEqual(rv['data']['content'], u'不错',
                         'comment content error!')
        resp = self.app.get('/videos/%s/comments/' % (self.VIDEO_ID))
        self.assertEqual(resp.status_code, 200, 'get video comments error')
        json_response = json.loads(resp.data)
        self.assertEqual(json_response['status'], 0)
        # 检查最新的评论是否存在并且在最顶
        self.assertEqual(json_response['data']['comments'][0]['comment_id'],
                         rv['data']['comment_id'], 'create comment is failed!')

        comment_id = rv['data']['comment_id']
        _data = dict(comment_id=comment_id, ut=self.UT)
        resp = self.app.post('/user/opt/delete-comment', data=_data)
        self.assertEqual(resp.status_code, 200, 'delete comment error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        _data = dict(comment_id=self.COMMENT_ID, ut=self.UT)
        resp = self.app.post('/user/opt/like-comment', data=_data)
        self.assertEqual(resp.status_code, 200, 'like comment error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        _data = dict(comment_id=self.COMMENT_ID, ut=self.UT)
        resp = self.app.post('/user/opt/unlike-comment', data=_data)
        self.assertEqual(resp.status_code, 200, 'unlike comment error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        resp = self.app.get('/videos/%s/comments/' % (self.VIDEO_ID))
        self.assertEqual(resp.status_code, 200, 'get video comments error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        # 本视频的评论在删除后和原始评论数一样
        self.assertEqual(len(rv['data']['comments']),
                         2, 'delete comments is failed!')
        self.assertEqual(rv['data']['comments'][0]['like'],
                         0, 'add like comments error!')
        resp = self.app.get('/videos/%s/comments/?maxs=0' % (self.VIDEO_ID))
        self.assertEqual(resp.status_code, 200, 'get video comments error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        # 评论回复相关测试
        _data = dict(comment_id=self.COMMENT_ID, content='test', ut=self.UT)
        resp = self.app.post('/replies/create', data=_data)
        self.assertEqual(resp.status_code, 200, 'create reply error')
        self.assertEqual(json.loads(resp.data)['status'], 0)
        _rid = json.loads(resp.data)['data']['reply']['reply_id']

        resp = self.app.get('/comment/%s/replies' % (self.COMMENT_ID))
        self.assertEqual(resp.status_code, 200, 'get replies error')
        ret = json.loads(resp.data)
        self.assertEqual(ret['status'], 0)
        self.assertEqual(len(ret['data']['replies']), 1)

        _data = dict(ut=self.UT)
        resp = self.app.post('/replies/%s/delete' % (_rid), data=_data)
        self.assertEqual(resp.status_code, 200, 'delete reply error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        resp = self.app.get('/comment/%s/replies' % (self.COMMENT_ID))
        self.assertEqual(resp.status_code, 200, 'get replies error')
        ret = json.loads(resp.data)
        self.assertEqual(ret['status'], 0)
        self.assertEqual(len(ret['data']['replies']), 0)

    def test_game(self):
        resp = self.app.get('/games')
        self.assertEqual(resp.status_code, 200, 'get games error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        resp = self.app.get('/games/host?game_id=%s' % (self.GAME_ID))
        self.assertEqual(resp.status_code, 200, 'get game host error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        resp = self.app.get('/games/%s/download' % (self.GAME_ID))
        self.assertEqual(resp.status_code, 200, 'get game download error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        resp = self.app.get('/games/%s/download' % (self.GAME_ID))
        self.assertEqual(resp.status_code, 200, 'get game download error')
        _data = json.loads(resp.data)
        self.assertEqual(_data['status'], 0)

        down_id = _data['data']['download_id']
        _data = dict(ut=self.UT)
        resp = self.app.post('/games/%s/finish_download' % (down_id), data=_data)
        self.assertEqual(resp.status_code, 200, 'finish download error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        resp = self.app.get('/users/%s/games' % (self.USER_ID))
        self.assertEqual(resp.status_code, 200, 'get user sub games error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(len(rv['data']['games']), 3, 'game num error!')
        self.assertEqual(rv['data']['games'][0]['game_id'],
                         '55efe64feb43a14b0fcff4e2', 'game seq error!')

        resp = self.app.get('/games/%s' % (self.GAME_ID))
        self.assertEqual(resp.status_code, 200, 'get game info error')
        self.assertEqual(json.loads(resp.data)['status'], 0)
        self.assertEqual(sorted(self.GAME_RETURN_KEYS),
                         sorted(json.loads(resp.data)['data'].keys()))
        self.assertIn('"game_id": "55efe64deb43a14b0fcff4e1"',
                      resp.data, "game info error!")

        resp = self.app.get('/channels/games')
        self.assertEqual(resp.status_code, 200, 'get channel games error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(len(rv['data']), 4, 'channel game num error!')
        self.assertEqual(rv['data'][0]['tag_id'], '55f670795961b21e819d5e00',
                         'channel game seq error!')

        resp = self.app.get('/tags/55f670795961b21e819d5e01/games')
        self.assertEqual(resp.status_code, 200, 'get tag games error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(rv['data']['games'][0]['game_id'],
                         '55efe64beb43a14b0fcff4df', 'games seq error!')

        _data = dict(game_id=self.GAME_ID, ut=self.UT)
        resp = self.app.post('/user/opt/subscribe-game', data=_data)
        self.assertEqual(resp.status_code, 200, 'sub game error')
        self.assertEqual(json.loads(resp.data)['status'], 0)
        resp = self.app.get('/users/%s/games' % (self.USER_ID))
        self.assertEqual(resp.status_code, 200, 'get user sub games error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(len(rv['data']['games']), 4, 'game num error!')
        self.assertEqual(rv['data']['games'][0]['game_id'],
                         self.GAME_ID, 'game seq error!')

        _data = dict(game_id=self.GAME_ID, ut=self.UT)
        resp = self.app.post('/user/opt/unsubscribe-game', data=_data)
        self.assertEqual(resp.status_code, 200, 'unsub game error')
        self.assertEqual(json.loads(resp.data)['status'], 0)
        resp = self.app.get('/users/%s/games' % (self.USER_ID))
        self.assertEqual(resp.status_code, 200, 'get user sub games error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(len(rv['data']['games']), 3, 'game num error!')
        self.assertEqual(rv['data']['games'][0]['game_id'],
                         '55efe64feb43a14b0fcff4e2', 'game seq error!')

        resp = self.app.get('/recommend/subscribe/games')
        self.assertEqual(resp.status_code, 200,
                         'get recommend subscribe games error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(len(rv['data']['games']), 3,
                         'recommend subscribe games num error!')

        resp = self.app.get('/games/home?os=android&version_code=320')
        self.assertEqual(resp.status_code, 200,
                         'get game ads error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(sorted(self.GAME_HOME_RETURN_KEYS),
                         sorted(rv['data'].keys()))

        resp = self.app.get('/games/grids?os=android')
        self.assertEqual(resp.status_code, 200,
                         'get game grids error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(len(rv['data']['grids']), 2,
                         'game grids num error!')

        resp = self.app.get('/games/ads?os=android&version_code=320')
        self.assertEqual(resp.status_code, 200,
                         'get game ads error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(len(rv['data']['ads']), 1,
                         'game ads num error!')

        resp = self.app.get('/games/topics?os=android&version_code=320')
        self.assertEqual(resp.status_code, 200,
                         'get game topics error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(len(rv['data']['topics']), 1,
                         'game topics num error!')

        topic_id = rv['data']['topics'][0]['id']
        resp = self.app.get('/games/topic_games?topic_id=%s' % topic_id)
        self.assertEqual(resp.status_code, 200,
                         'get topic games error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(len(rv['data']['games']), 3,
                         'topic games num error!')

        resp = self.app.get('/games/mainstays?os=android&version_code=320')
        self.assertEqual(resp.status_code, 200,
                         'get game mainstays error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(len(rv['data']['mainstays']), 1,
                         'game mainstays num error!')

        resp = self.app.get('/games/modules?os=android')
        self.assertEqual(resp.status_code, 200,
                         'get game modules error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(len(rv['data']['modules']), 2,
                         'game modules num error!')

        resp = self.app.get('/games/module_games?module_id=5785b124bf98d91830c6e5cd')
        self.assertEqual(resp.status_code, 200,
                         'get module games error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(len(rv['data']['games']), 1,
                         'module games num error!')


    def test_web_game(self):
        resp = self.app.get('/webgames')
        self.assertEqual(resp.status_code, 200, 'get web games error')
        self.assertEqual(json.loads(resp.data)['status'], 0)
        self.assertEqual(json.loads(resp.data)['data']['games'].__len__(), 1)

        resp = self.app.get('/webgames/ads?os=android&version_code=320')
        self.assertEqual(resp.status_code, 200,
                         'get webgame ads error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(len(rv['data']['ads']), 1,
                         'webgame ads num error!')

    def test_user(self):
        name = 'unittest_%s' % (random.randint(1000, 9999))
        _data = dict(name=name, password='abcd1234',
                     nickname=random.randint(111111, 999999))
        resp = self.app.post('/users/register', data=_data)
        self.assertEqual(resp.status_code, 200, 'user register error')
        self.assertEqual(json.loads(resp.data)['status'], 0)
        self.assertEqual(sorted(self.USER_RETURN_KEYS),
                         sorted(json.loads(resp.data)['data']['user'].keys()))
        self.assertIn(name, resp.data, 'user register info error!')
        self.assertIn('"ut":', resp.data, 'user token error!')

        _data = dict(name=name, password='abcd1234')
        resp = self.app.post('/users/login', data=_data)
        self.assertEqual(resp.status_code, 200, 'user login error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        _data = dict(name='18688888888', password='abcd1234', type='phone')
        resp = self.app.post('/users/login', data=_data)
        self.assertEqual(resp.status_code, 200, 'user login error')
        self.assertEqual(json.loads(resp.data)['status'], 0)
        self.assertEqual(sorted(self.USER_RETURN_KEYS),
                         sorted(json.loads(resp.data)['data']['user'].keys()))
        self.assertIn('"user_id": "56246d292d7fa20787d683b4"',
                      resp.data, 'user info error')
        self.assertIn('"ut":', resp.data, 'user token error!')

        _data = dict(old_pwd='abcd1234', new_pwd='1234abcd', ut=self.UT)
        resp = self.app.post('/users/%s/change-password' %
                             (self.USER_ID), data=_data)
        self.assertEqual(resp.status_code, 200, 'user change pwd error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        _data = dict(old_pwd='1234abcd', new_pwd='abcd1234', ut=self.UT)
        resp = self.app.post('/users/%s/change-password' %
                             (self.USER_ID), data=_data)
        self.assertEqual(resp.status_code, 200, 'user change pwd error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        _data = dict(ut=self.UT)
        resp = self.app.post('/users/refresh_token', data=_data)
        self.assertEqual(resp.status_code, 200, 'user refresh token error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        resp = self.app.get('/users/verify_nickname?nickname=%s' % ('轻口味'))
        self.assertEqual(resp.status_code, 200, 'verify nickname error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], -10020)

        resp = self.app.get('/users/verify_phone?phone=%s' % ('18688888888'))
        self.assertEqual(resp.status_code, 200, 'verify phone error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], -10004)

        _data = dict(
            nickname='Dongin%s' % (random.randint(1000, 9999)),
            birthday='19881218',
            email='unittest@wonxing.com',
            gender=1,
            ut=self.UT,
            signature=u'大魔头之罪恶王座',
        )
        resp = self.app.post('/users/%s/modify-info' %
                             (self.USER_ID), data=_data)
        self.assertEqual(resp.status_code, 200, 'user modify info error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(rv['data']['user']['nickname'],
                         _data['nickname'], 'change nickname failed')
        self.assertEqual(rv['data']['user']['gender'], _data[
            'gender'], 'change gender failed')

        _data = dict(
            nickname='轻口味',
            ut=self.UT
        )
        resp = self.app.post('/users/%s/modify-info' %
                             (self.USER_ID), data=_data)
        self.assertEqual(resp.status_code, 200, 'user modify nickname error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], -10020)

        invalid_nicks = ['轻a', 'abc', '这真不是一个合法的昵称',
                         'abcabcabcabcabcagcagc', '轻轻@']
        for nickname in invalid_nicks:
            _data = dict(
                nickname=nickname,
                ut=self.UT
            )
            resp = self.app.post('/users/%s/modify-info' %
                                 (self.USER_ID), data=_data)
            self.assertEqual(resp.status_code, 200,
                             'user modify nickname error')
            rv = json.loads(resp.data)
            self.assertEqual(rv['status'], -10021)

        valid_nicks = ['轻轻', 'abcd', '轻轻abd', '轻轻123', 'abc123']
        for nickname in valid_nicks:
            _data = dict(
                nickname=nickname,
                ut=self.UT
            )
            resp = self.app.post('/users/%s/modify-info' %
                                 (self.USER_ID), data=_data)
            self.assertEqual(resp.status_code, 200,
                             'user modify nickname error')
            rv = json.loads(resp.data)
            self.assertEqual(rv['status'], 0)

        _data = dict(target_user_id=self.TARGET_USER_ID, ut=self.UT)
        resp = self.app.post('/user/opt/follow-user', data=_data)
        self.assertEqual(resp.status_code, 200, 'user register error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        _data = dict(target_user_id=self.TARGET_USER_ID, ut=self.UT)
        resp = self.app.post('/user/opt/unfollow-user', data=_data)
        self.assertEqual(resp.status_code, 200, 'user register error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        resp = self.app.get('/users/%s' % (self.USER_ID))
        self.assertEqual(resp.status_code, 200, 'get user info error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertIsNotNone(rv.get('data', None))

        resp = self.app.get('/users/%s/followers' % (self.USER_ID))
        self.assertEqual(resp.status_code, 200, 'get user followers error')
        rv = json.loads(resp.data)
        self.assertEqual(len(rv['data']['users']), 4, 'user followers num error!')

        resp = self.app.get('/users/%s/followings' % (self.USER_ID))
        self.assertEqual(resp.status_code, 200, 'get user followings error')
        rv = json.loads(resp.data)
        self.assertEqual(len(rv['data']['users']), 2, 'user followings num error!')

        resp = self.app.get('/games/%s/popularusers' % (self.GAME_ID))
        self.assertEqual(resp.status_code, 200, 'get game pop users error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        resp = self.app.get('/recommend/users?ut=%s' % (self.UT))
        self.assertEqual(resp.status_code, 200, 'get recommend users error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        resp = self.app.get('/users/contacts?ut=%s' % (self.UT))
        self.assertEqual(resp.status_code, 200, 'get user contacts error')
        rv = json.loads(resp.data)
        self.assertEqual(len(rv['data']['users']), 2, 'user contact num error!')

        _data = dict(platform='qq', target_type='video', target_value=self.VIDEO_ID, ut=self.UT)
        resp = self.app.post('/users/share', data=_data)
        self.assertEqual(resp.status_code, 200, 'user share error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

    def test_video(self):
        _data = dict(
            game_id=self.GAME_ID,
            title='真是好看啊',
            duration=120,
            ratio='1280x800',
            ut=self.UT
        )
        resp = self.app.post('/videos/new-video', data=_data)
        self.assertEqual(resp.status_code, 200, 'create video error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(sorted(self.VIDEO_RETURN_KEYS),
                         sorted(rv['data'].keys()))

        video_id = rv['data']['video_id']
        import hashlib
        md5 = hashlib.md5(video_id)
        secret = '&%s' % ('29eb78ff3c8f20fe')
        md5.update(secret)
        data = dict(cover='test.jpg', url='test.mp4', upload_sig=md5.hexdigest())
        resp = self.app.post('/videos/%s/update-video' %
                             (video_id), data=data)
        self.assertEqual(resp.status_code, 200, 'update video error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        data = dict(title=u'新的视频标题', ut=self.UT)
        resp = self.app.post('/videos/%s/modify-video' %
                             (video_id), data=data)
        self.assertEqual(resp.status_code, 200, 'modify video error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(rv['data']['video']['title'], u'新的视频标题')

        resp = self.app.post('/videos/%s/delete' %
                             (video_id), data=dict(ut=self.UT))
        self.assertEqual(resp.status_code, 200, 'delete video error')
        self.assertEqual(json.loads(resp.data)['status'], 0)
        resp = self.app.get('/videos/%s' % (video_id))
        self.assertEqual(resp.status_code, 200, 'get video info error')
        self.assertEqual(json.loads(resp.data)[
                             'status'], -10011, 'delete video info failed')

        resp = self.app.get('/videos/%s' % (self.VIDEO_ID))
        self.assertEqual(resp.status_code, 200, 'get video info error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(sorted(self.VIDEO_RETURN_KEYS),
                         sorted(rv['data'].keys()))
        self.assertEqual(rv['data']['video_id'],
                         self.VIDEO_ID, 'video info error')

        resp = self.app.get('/videos/%s/play?ut=%s' % (self.VIDEO_ID, self.UT))
        self.assertEqual(resp.status_code, 302, 'play video error')

        resp = self.app.get('/videos/%s/play' % ('561e206deb43a13470715f28'))
        self.assertEqual(resp.status_code, 200, 'play video error')
        self.assertEqual(json.loads(resp.data)['status'], -10011)

        _data = dict(video_id=self.VIDEO_ID, ut=self.UT)
        resp = self.app.post('/user/opt/favorite-video', data=_data)
        self.assertEqual(resp.status_code, 200, 'favor video error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        _data = dict(video_id=self.VIDEO_ID, ut=self.UT)
        resp = self.app.post('/user/opt/unfavorite-video', data=_data)
        self.assertEqual(resp.status_code, 200, 'unfavor video error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        _data = dict(video_id=self.VIDEO_ID, ut=self.UT)
        resp = self.app.post('/user/opt/like-video', data=_data)
        self.assertEqual(resp.status_code, 200, 'like video error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        _data = dict(video_id=self.VIDEO_ID, ut=self.UT)
        resp = self.app.post('/user/opt/unlike-video', data=_data)
        self.assertEqual(resp.status_code, 200, 'unlike video error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        resp = self.app.get('/videos/current/')
        self.assertEqual(resp.status_code, 200, 'get current videos error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(len(rv['data']['videos']), 4, 'videos num error!')
        self.assertEqual(rv['data']['videos'][0]['video_id'],
                         '55efe87aeb43a14de2d05fd3', 'videos seq error!')
        resp = self.app.get('/videos/current/?maxs=0')
        self.assertEqual(resp.status_code, 200, 'get current videos error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        resp = self.app.get('/users/%s/favors' % (self.USER_ID))
        self.assertEqual(resp.status_code, 200, 'get favor videos error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(len(rv['data']['videos']),
                         3, 'favor videos num error')
        self.assertEqual(rv['data']['videos'][0]['video_id'],
                         '55efe87aeb43a14de2d05fd3', 'favor videos seq error')
        resp = self.app.get('/users/%s/favors?maxs=0' % (self.USER_ID))
        self.assertEqual(resp.status_code, 200, 'get favor videos error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        resp = self.app.get('/users/%s/subscriptions' % (self.USER_ID))
        self.assertEqual(resp.status_code, 200, 'get sub game videos error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        resp = self.app.get('/users/%s/videos' % (self.USER_ID))
        self.assertEqual(resp.status_code, 200, 'get user videos error')
        self.assertEqual(json.loads(resp.data)['status'], 0)
        resp = self.app.get('/users/%s/videos?maxs=0' % (self.USER_ID))
        self.assertEqual(resp.status_code, 200, 'get user videos error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        resp = self.app.get('/users/%s/live_videos?maxs=0' % (self.USER_ID))
        self.assertEqual(resp.status_code, 200, 'get user live videos error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        resp = self.app.get('/users/%s/videos?game_id=%s' %
                            (self.USER_ID, self.GAME_ID))
        self.assertEqual(resp.status_code, 200, 'get user videos error')
        self.assertEqual(json.loads(resp.data)['status'], 0)
        resp = self.app.get('/users/%s/videos?game_id=%s&maxs=0' %
                            (self.USER_ID, self.GAME_ID))
        self.assertEqual(resp.status_code, 200, 'get user videos error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        resp = self.app.get('/games/%s/videos' % (self.GAME_ID))
        self.assertEqual(resp.status_code, 200, 'get game videos error')
        self.assertEqual(json.loads(resp.data)['status'], 0)
        resp = self.app.get('/games/%s/videos?maxs=0' % (self.GAME_ID))
        self.assertEqual(resp.status_code, 200, 'get game videos error')
        self.assertEqual(json.loads(resp.data)['status'], 0)
        resp = self.app.get('/games/%s/videos?orderby=vv' % (self.GAME_ID))
        self.assertEqual(resp.status_code, 200, 'get game videos error')
        self.assertEqual(json.loads(resp.data)['status'], 0)
        resp = self.app.get(
            '/games/%s/videos?orderby=vv&maxs=0' % (self.GAME_ID))
        self.assertEqual(resp.status_code, 200, 'get game videos error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        resp = self.app.get('/games/%s/live_videos?maxs=0' % (self.GAME_ID))
        self.assertEqual(resp.status_code, 200, 'get game live videos error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        resp = self.app.get('/games/%s/popular/videos?maxs=0' % (self.GAME_ID))
        self.assertEqual(resp.status_code, 200,
                         'get game popular videos error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        resp = self.app.get('/users/%s/followings/videos?ut=%s' %
                            (self.USER_ID, self.UT))
        self.assertEqual(resp.status_code, 200,
                         'get user followings videos error')
        self.assertEqual(json.loads(resp.data)['status'], 0)
        resp = self.app.get(
            '/users/%s/followings/videos?maxs=0&ut=%s' % (self.USER_ID, self.UT))
        self.assertEqual(resp.status_code, 200,
                         'get user followings videos error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        resp = self.app.get('/tags/%s/videos' % ('55f670795961b21e819d5e00'))
        self.assertEqual(resp.status_code, 200, 'get tag videos error')
        self.assertEqual(json.loads(resp.data)['status'], 0)
        resp = self.app.get('/tags/%s/videos?maxs=0' %
                            ('55f670795961b21e819d5e00'))
        self.assertEqual(resp.status_code, 200, 'get tag videos error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        resp = self.app.get('/share/video/%s' % (self.VIDEO_ID))
        self.assertEqual(resp.status_code, 200, 'share video error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        resp = self.app.get('/videos/event_id?event_id=1')
        self.assertEqual(resp.status_code, 200, 'get video id error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        resp = self.app.get('/videos/categories?game_id=55efe64feb43a14b0fcff4e3')
        self.assertEqual(resp.status_code, 200, 'get video categories error')
        self.assertEqual(json.loads(resp.data)['status'], 0)
        rv = json.loads(resp.data)
        self.assertEqual(len(rv['data']['categories']), 1)

        _url = "/videos/category_videos?category_id=%s&game_id=%s&maxs=0"
        _url = _url % ('57357dc62d7fa213a641fb89', '55efe64feb43a14b0fcff4e3')
        resp = self.app.get(_url)
        self.assertEqual(resp.status_code, 200, 'get category videos error')
        self.assertEqual(json.loads(resp.data)['status'], 0)
        rv = json.loads(resp.data)
        self.assertEqual(len(rv['data']['videos']), 1)

        resp = self.app.get('/videos/topics')
        self.assertEqual(resp.status_code, 200, 'get video topics error')
        self.assertEqual(json.loads(resp.data)['status'], 0)
        rv = json.loads(resp.data)
        self.assertEqual(len(rv['data']['topics']), 2)

        _url = "/videos/topic_videos?topic_id=%s&maxs=0"
        _url = _url % rv['data']['topics'][0]['topic_id']
        resp = self.app.get(_url)
        self.assertEqual(resp.status_code, 200, 'get topic videos error')
        self.assertEqual(json.loads(resp.data)['status'], 0)
        rv = json.loads(resp.data)
        self.assertEqual(len(rv['data']['videos']), 1)

    def test_share(self):
        resp = self.app.get('/share/page/%s' % (self.VIDEO_ID))
        self.assertEqual(resp.status_code, 200, 'share page error')

    def test_migu(self):
        resp = self.app.get('/migu/home/')
        self.assertEqual(resp.status_code, 200, 'migu home error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)

        resp = self.app.get('/migu/users/88888888/videos/')
        self.assertEqual(resp.status_code, 200, 'migu user video error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)

        _data = dict(user_id='88888888', content='不错', ut=self.UT)
        resp = self.app.post('/migu/videos/%s/comments/submit' %
                             (self.MIGU_VIDEO_ID), data=_data)
        rv = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200, 'create comment error')
        self.assertEqual(rv['status'], 0)

        resp = self.app.get('/migu/videos/%s/comments/?maxs=0' % (self.VIDEO_ID))
        self.assertEqual(resp.status_code, 200, 'get migu video comments error')
        json_response = json.loads(resp.data)
        self.assertEqual(json_response['status'], 0)

        resp = self.app.get('/migu/games/760000041207/popular/')
        self.assertEqual(resp.status_code, 200, 'migu game pop video error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)

        resp = self.app.get('/migu/tags/home/')
        self.assertEqual(resp.status_code, 200, 'migu game pop video error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)

        # _data = dict(token='ai123456', openid='18801158983', platform='migu')
        # resp = self.app.post('/partner/users/login', data=_data)
        # self.assertEqual(resp.status_code, 200, 'user change pwd error')
        # self.assertEqual(json.loads(resp.data)['status'], 0)

        # _data = dict(old_pwd='ai123456', new_pwd='ai891101',
        #              phone='18801158983')
        # resp = self.app.post('/migu/change_password', data=_data)
        # self.assertEqual(resp.status_code, 200, 'user change pwd error')
        # self.assertEqual(json.loads(resp.data)['status'], -10016)

        # _data = dict(old_pwd='ai891101', new_pwd='ai123456',
        #              phone='18801158983')
        # resp = self.app.post('/migu/change_password', data=_data)
        # self.assertEqual(resp.status_code, 200, 'user change pwd error')
        # self.assertEqual(json.loads(resp.data)['status'], -10018)

        # _data = dict(phone='15850510086')
        # resp = self.app.post('/migu/verify_phone', data=_data)
        # self.assertEqual(resp.status_code, 200, 'verify phone error')
        # self.assertEqual(json.loads(resp.data)['status'], -10004)

    def test_upload(self):
        kw_path = app.config.get('BASE_DIR') or os.path.abspath(
            os.path.join(app.root_path, '../'))
        fname = os.path.join(kw_path, 'wanx/tests/fixtures/test.jpg')
        data = dict(
            {'file': (fname, 'test.jpg')},
            type='users.photo',
            target_id=self.USER_ID,
            ut=self.UT
        )
        resp = self.app.post('/upload/upload-small-file',
                             content_type='multipart/form-data',
                             data=data)
        rv = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200, 'upload file error')
        self.assertEqual(rv['status'], 0)
        self.assertEqual(rv['data']['url'].replace("\\", "/"), urljoin(app.config.get('STATIC_URL'),
                                                                       '/images/6ed/6ed0dae42606409b4f7907bf8e3753d5.jpg'))

    def test_upload_large(self):
        data = dict(
            type='videos.url',
            ut=self.UT,
            target_id='55efe87aeb43a14de2d05fd0',
            size=1579684,
            ext='mp4'
        )
        resp = self.app.post('/upload/upload-large-file',
                             content_type='multipart/form-data',
                             data=data)
        rv = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200, 'upload large file error')
        self.assertEqual(rv['status'], 0)

        upload_url = '%s?ut=%s' % (rv['data']['url'], self.UT)
        kw_path = app.config.get('BASE_DIR') or os.path.abspath(
            os.path.join(app.root_path, '../'))
        fname = os.path.join(kw_path, 'wanx/tests/fixtures/test.mp4')
        resp = None
        with open(fname, 'rb') as f:
            rngs = range(0, 1579684, 1024 * 10)
            for offset in rngs:
                f.seek(offset)
                data = f.read(1024 * 15)
                headers = {'Range': 'bytes=%d-%d' % (offset, len(data))}
                resp = self.app.put(upload_url, data=data, headers=headers,
                                    content_type='application/octet-stream')
                self.assertEqual(resp.status_code, 200,
                                 'upload large file error')
                rv = json.loads(resp.data)
                self.assertEqual(rv['status'], 0)
                if rv['data']['complete']:
                    break

        rv = json.loads(resp.data)
        self.assertEqual(rv['data']['url'].replace("\\", "/"), urljoin(app.config.get('STATIC_URL'),
                                                                       '/videos/231/23114f999ff0f95cd071eff17614fdf4.mp4'))

    def test_msg(self):
        resp = self.app.get('/messages/home?ut=%s' % (self.UT))
        self.assertEqual(resp.status_code, 200, 'msg home error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)

        data = dict(ut=self.UT, lrt=time.time())
        resp = self.app.post('/messages/delete', data=data)
        self.assertEqual(resp.status_code, 200, 'delete msg error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)

        resp = self.app.get('/letters/detail?ut=%s&sender=%s' %
                            (self.UT, self.TARGET_USER_ID))
        self.assertEqual(resp.status_code, 200, 'letter detail error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)

        data = dict(ut=self.UT, sender=self.TARGET_USER_ID, lrt=time.time())
        resp = self.app.post('/letters/delete', data=data)
        self.assertEqual(resp.status_code, 200, 'delete letter error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)

        data = dict(ut=self.UT, receiver=self.TARGET_USER_ID,
                    content='test123')
        resp = self.app.post('/letters/send', data=data)
        self.assertEqual(resp.status_code, 200, 'send letter error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)

        data = dict(ut=self.UT, contact='1861881888', content='觉得这个游戏不错')
        resp = self.app.post('/suggestion/commit', data=data)
        self.assertEqual(resp.status_code, 200, 'commit suggestion error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)

    def test_traffic(self):
        sign = md5(''.join([self.USER_ID, self.VIDEO_ID, str(20151212)])).hexdigest()[
               2:24]
        _data = dict(user_id=self.USER_ID,
                     sign=sign,
                     target_id=self.VIDEO_ID,
                     timestamp=20151212,
                     ut=self.UT,
                     traffic_type='video_share',
                     platform='qq')
        resp = self.app.post('/traffic', data=_data)
        self.assertEqual(resp.status_code, 200, 'users traffic error')
        self.assertIn(json.loads(resp.data)['status'], [0, -10026])

        _data = dict(user_id=self.USER_ID,
                     ut=self.UT,
                     traffic_type='video_share')
        resp = self.app.post('/traffic/send', data=_data)
        self.assertEqual(resp.status_code, 200, 'traffic send error')
        self.assertIn(json.loads(resp.data)['status'], [0, -10032])

        _data = dict(user_id=self.USER_ID,
                     ut=self.UT,
                     traffic_type='video_share')
        resp = self.app.post('/traffic/search', data=_data)
        self.assertEqual(resp.status_code, 200, 'traffic search error')
        self.assertIn(json.loads(resp.data)['data']['traffic_status'], [0, -1])

        resp = self.app.post('/traffic/message', data=self.xml)
        self.assertEqual(resp.status_code, 200, 'traffic message error')

    def test_live(self):
        resp = self.app.get('/lives/cate-games?ut=%s' % (self.UT))
        self.assertEqual(resp.status_code, 200, 'get cate-games error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(len(rv['data']['games']), 4)

        resp = self.app.get('/lives/recommend?ut=%s' % (self.UT))
        self.assertEqual(resp.status_code, 200, 'get recommend lives error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(len(rv['data']['lives']), 3)
        self.assertTrue(rv['data']['lives'][0]['from_following'])

        resp = self.app.get('/lives/game', data=dict(gid='55efe64beb43a14b0fcff4de'))
        self.assertEqual(resp.status_code, 200, 'get game lives error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(len(rv['data']['lives']), 2)

        resp = self.app.get('/lives/info?ut=%s&live_id=10002&os=android&version_code=320' % (self.UT))
        self.assertEqual(resp.status_code, 200, 'get live info error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(rv['data']['live']['event_id'], '10002')

        resp = self.app.get('/lives/play?ut=%s&live_id=10002&os=android&version_code=320' % (self.UT))
        self.assertEqual(resp.status_code, 200, 'play live error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(rv['data']['ret'], True)

        resp = self.app.get('/lives/share?ut=%s&live_id=10002' % (self.UT))
        self.assertEqual(resp.status_code, 200, 'share live error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(rv['data']['ret'], True)

    def test_task(self):
        resp = self.app.get('/credit/user?ut=%s' % (self.UT))
        self.assertEqual(resp.status_code, 200, 'get user credit error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(rv['data']['gem'], 0)
        self.assertEqual(rv['data']['gold'], 0)

        resp = self.app.get('/task/user_tasks?ut=%s' % (self.UT))
        self.assertEqual(resp.status_code, 200, 'get user tasks error')
        rv = json.loads(resp.data)
        self.assertEqual(len(rv['data']['daily_tasks']), 7)
        self.assertEqual(len(rv['data']['novice_tasks']), 7)
        self.assertEqual(len(rv['data']['game_tasks']), 1)

    def test_task_finished(self):
        for task_id in range(1, 16):
            _data = dict(task_id=task_id, ut=self.UT)
            resp = self.app.post('/task/receive_reward', data=_data)
            self.assertEqual(resp.status_code, 200, 'receive reward error')
            rv = json.loads(resp.data)
            self.assertEqual(len(rv['data']['rewards']), 1)

        resp = self.app.get('/credit/user?ut=%s' % (self.UT))
        self.assertEqual(resp.status_code, 200, 'get user credit error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(rv['data']['gem'], 200)
        self.assertEqual(rv['data']['gold'], 2350)

        resp = self.app.get('/credit/gold_log?ut=%s&nbr=20' % (self.UT))
        self.assertEqual(resp.status_code, 200, 'get gold log error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(len(rv['data']['logs']), 14)
        self.assertEqual(sum([log['gold'] for log in rv['data']['logs']]), 2350)

        resp = self.app.get('/credit/gem_log?ut=%s&nbr=20' % (self.UT))
        self.assertEqual(resp.status_code, 200, 'get gem log error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(len(rv['data']['logs']), 1)
        self.assertEqual(sum([log['gem'] for log in rv['data']['logs']]), 200)

    def test_gift(self):
        resp = self.app.get('/gifts/all_gifts?ut=%s' % (self.UT))
        self.assertEqual(resp.status_code, 200, 'get all gift error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(len(rv['data']['gifts']), 2)

        _data = dict(ut=self.UT, user_id=self.TARGET_USER_ID, gift_id=1,
                     num=1, gift_from=2, from_id='55efe87aeb43a14de2d05fd3')
        resp = self.app.post('/gifts/send_gift', data=_data)
        self.assertEqual(resp.status_code, 200, 'get all gift error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(rv['data']['ret'], True)

        _data = dict(ut=self.UT, user_id=self.TARGET_USER_ID, gift_id=1,
                     num=1, gift_from=2, from_id='55efe87aeb43a14de2d05fd3')
        resp = self.app.post('/gifts/send_gift', data=_data)
        self.assertEqual(resp.status_code, 200, 'get all gift error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], -10040)

        _data = dict(ut=self.UT, user_id=self.TARGET_USER_ID, gift_id=2,
                     num=1, gift_from=2, from_id='55efe87aeb43a14de2d05fd3')
        resp = self.app.post('/gifts/send_gift', data=_data)
        self.assertEqual(resp.status_code, 200, 'send gift error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(rv['data']['ret'], True)

        _data = dict(ut=self.UT, user_id=self.TARGET_USER_ID, gift_id=2,
                     num=1, gift_from=2, from_id='55efe87aeb43a14de2d05fd3')
        resp = self.app.post('/gifts/send_gift', data=_data)
        self.assertEqual(resp.status_code, 200, 'send gift error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(rv['data']['ret'], True)

        _data = dict(ut=self.UT, user_id=self.TARGET_USER_ID, gift_id=2,
                     num=1, gift_from=2, from_id='55efe87aeb43a14de2d05fd3')
        resp = self.app.post('/gifts/send_gift', data=_data)
        self.assertEqual(resp.status_code, 200, 'send gift error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], -10040)

        resp = self.app.get('/credit/user?ut=%s' % (self.UT))
        self.assertEqual(resp.status_code, 200, 'get user credit error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(rv['data']['gem'], 200)
        self.assertEqual(rv['data']['gold'], 350)

        resp = self.app.get('/gifts/user_gifts?ut=%s' % (self.TARGET_UT))
        self.assertEqual(resp.status_code, 200, 'get user gift error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(len(rv['data']['gifts']), 2)
        for gf in rv['data']['gifts']:
            if gf['product_id'] == 2:
                self.assertEqual(gf['num'], 1)
            elif gf['product_id'] == 3:
                self.assertEqual(gf['num'], 2)
            else:
                self.assertTrue(False)

        resp = self.app.get('/gifts/top_users?user_id=%s' % (self.TARGET_USER_ID))
        self.assertEqual(resp.status_code, 200, 'get sedn top user error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(len(rv['data']['users']), 1)
        self.assertEqual(rv['data']['users'][0]['total_gold'], 2100)

    def test_store(self):
        resp = self.app.get('/store/all_exchanges?ut=%s' % (self.UT))
        self.assertEqual(resp.status_code, 200, 'get exchanges error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(len(rv['data']['stores']), 1)
        self.assertEqual(len(rv['data']['stores'][0]['items']), 3)

        resp = self.app.get('/store/all_lotteries?ut=%s' % (self.UT))
        self.assertEqual(resp.status_code, 200, 'get lotteries error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(len(rv['data']['stores']), 1)

        # resp = self.app.get('/store/lottery_info?ut=%s&store_id=1' % (self.UT))
        # self.assertEqual(resp.status_code, 200, 'get lottery info error')
        # rv = json.loads(resp.data)
        # self.assertEqual(rv['status'], 0)
        # self.assertEqual(len(rv['data']['lottery']['items']), 6)

        # resp = self.app.get('/credit/user?ut=%s' % (self.UT))
        # self.assertEqual(resp.status_code, 200, 'get user credit error')
        # rv = json.loads(resp.data)
        # self.assertEqual(rv['status'], 0)
        # self.assertEqual(rv['data']['gold'], 100)

        # _data = dict(store_id=1, ut=self.UT)
        # resp = self.app.post('/store/draw_lottery', data=_data)
        # rv = json.loads(resp.data)
        # self.assertEqual(resp.status_code, 200, 'draw lottery error')
        # self.assertEqual(rv['status'], 0)
        # self.assertEqual(rv['data']['item']['left_num'], 19)
        # self.assertEqual(rv['data']['item']['use_num'], 1)

        # gold = 5090 if int(rv['data']['item']['product']['product_id']) == 1 else 90  # 抽中游米
        # resp = self.app.get('/credit/user?ut=%s' % (self.UT))
        # self.assertEqual(resp.status_code, 200, 'get user credit error')
        # rv = json.loads(resp.data)
        # self.assertEqual(rv['status'], 0)
        # self.assertEqual(rv['data']['gold'], gold)

        # resp = self.app.get('/store/user_orders?ut=%s&store_id=1&page=1&nbr=10' % (self.UT))
        # self.assertEqual(resp.status_code, 200, 'get user credit error')
        # rv = json.loads(resp.data)
        # self.assertEqual(rv['status'], 0)
        # self.assertEqual(len(rv['data']['orders']), 1)

    def test_activity(self):

        _data = dict(activity_id=self.ACTIVITY_ID, content='习近平', ut=self.UT)
        resp = self.app.post('/activity/user/submit-comment', data=_data)
        rv = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200, 'create activity comment error')
        self.assertEqual(rv['status'], -10003)

        _data = dict(activity_id=self.ACTIVITY_ID, content='不错', ut=self.UT)
        resp = self.app.post('/activity/user/submit-comment', data=_data)
        rv = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200, 'create activity comment error')
        self.assertEqual(rv['status'], 0)
        # 检查发表评论和返回评论是否一致
        self.assertEqual(rv['data']['content'], u'不错',
                         'comment content error!')
        resp = self.app.get('/activity/%s/comments' % (self.ACTIVITY_ID))
        self.assertEqual(resp.status_code, 200, 'get activity comments error')
        json_response = json.loads(resp.data)
        self.assertEqual(json_response['status'], 0)
        # 检查最新的评论是否存在并且在最顶
        self.assertEqual(json_response['data']['comments'][0]['comment_id'],
                         rv['data']['comment_id'], 'create activity comment is failed!')

        comment_id = rv['data']['comment_id']
        _data = dict(comment_id=comment_id, ut=self.UT)
        resp = self.app.post('/activity/user/delete-comment', data=_data)
        self.assertEqual(resp.status_code, 200, 'delete activity comment error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        _data = dict(comment_id=self.ACTIVITY_COMMENT_ID, ut=self.UT)
        resp = self.app.post('/activity/user/like-comment', data=_data)
        self.assertEqual(resp.status_code, 200, 'like activity comment error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        _data = dict(comment_id=self.ACTIVITY_COMMENT_ID, ut=self.UT)
        resp = self.app.post('/activity/user/unlike-comment', data=_data)
        self.assertEqual(resp.status_code, 200, 'unlike activity comment error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        resp = self.app.get('/activity/%s/comments' % (self.ACTIVITY_ID))
        self.assertEqual(resp.status_code, 200, 'get activity comments error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(len(rv['data']['comments']), 4)

        # 以下为活动视频相关接口测试
        resp = self.app.get('/activity/%s/compete_videos?ut=%s' % (self.ACTIVITY_ID, self.UT))
        self.assertEqual(resp.status_code, 200, 'get compete video error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(len(rv['data']['videos']), 1)

        _data = dict(video_id='55efe87aeb43a14de2d05fd1', ut=self.UT)
        resp = self.app.post('/activity/56f1119f421aa983702175d6/new-video', data=_data)
        self.assertEqual(resp.status_code, 200, 'create activity new video error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)

        resp = self.app.get('/activity/%s/videos?ut=%s&type=end' % (self.ACTIVITY_ID, self.UT))
        self.assertEqual(resp.status_code, 200, 'get my activity video error')
        json_response = json.loads(resp.data)
        self.assertEqual(json_response['status'], 0)

        _data = dict(activity_video=rv['data']['activity_video'], ut=self.UT)
        resp = self.app.post('/activity/56f1119f421aa983702175d6/delete/videos', data=_data)
        self.assertEqual(resp.status_code, 200, 'delete activity video error')
        self.assertEqual(json.loads(resp.data)['status'], 0)

        resp = self.app.get('/activity/%s/popular/videos' % (self.ACTIVITY_ID))
        self.assertEqual(resp.status_code, 200, 'get activity popular video error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)

        resp = self.app.get('/activity/%s/config' % (self.ACTIVITY_ID))
        self.assertEqual(resp.status_code, 200, 'get activity config error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)

        resp = self.app.get('/activity/56f1119f421aa983702175d6/video/current?maxs=0')
        self.assertEqual(resp.status_code, 200, 'get current videos error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(rv['data']['activity_videos'][0]['video_id'], '55efe87aeb43a14de2d05fd3')

        resp = self.app.get('/activity/56f1119f421aa983702175d6/top/videos')
        self.assertEqual(resp.status_code, 200, 'get top videos error')
        rv = json.loads(resp.data)
        self.assertEqual(rv['status'], 0)
        self.assertEqual(rv['data']['activity_videos'][0]['video_id'], '55efe87aeb43a14de2d05fd3')
