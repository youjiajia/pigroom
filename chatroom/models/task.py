# -*- coding: utf8 -*-
from urlparse import urljoin
from playhouse.shortcuts import model_to_dict, dict_to_model
from wanx import app
from wanx.base import util, const
from wanx.base.xmysql import MYDB
from wanx.base.xredis import Redis, MRedis
from wanx.models import BaseModel
from wanx.models.game import Game, GameActivity
from wanx.models.credit import UserCredit
from wanx.models.product import Product
from wanx.models.user import User

import cPickle as cjson
import datetime
import peewee as pw
import json


TASK_KEY = 'task:all'
USER_TASK_KEY = 'task:user:%s'

NOVICE_TASK = 1
DAILY_TASK = 2
GAME_TASK = 3
ACTIVITY_TASK = 4

DAILY_SIGNIN = 1
PLAY_VIDEO = 2
CREATE_VIDEO = 3
COMMENT_VIDEO = 4
SHARE_VIDEO = 5
SET_HEADER = 6
SUB_GAME = 7
FOLLOW_USER = 8
DOWNLOAD_GAME = 9
PLAY_LIVE = 10
SHARE_LIVE = 11
BEGIN_LIVE = 12
JOIN_COLLECT = 13

UNFINISHED = 1
FINISHED = 2
RECEIVED = 3

ALL_PLATFORM = 1
ANDROID_ONLY = 2
IOS_ONLY = 3

TASK_TYPE = (
    (NOVICE_TASK, u'新手任务'),
    (DAILY_TASK, u'日常任务'),
    (GAME_TASK, u'游戏任务'),
    (ACTIVITY_TASK, u'活动任务'),
)

TASK_ACTION = (
    (DAILY_SIGNIN, u'每日签到次数'),
    (PLAY_VIDEO, u'观看视频次数'),
    (CREATE_VIDEO, u'发布视频次数'),
    (COMMENT_VIDEO, u'发表评论次数'),
    (SHARE_VIDEO, u'分享视频次数'),
    (SET_HEADER, u'设置头像次数'),
    (SUB_GAME, u'订阅游戏次数'),
    (FOLLOW_USER, u'关注主播次数'),
    (DOWNLOAD_GAME, u'下载游戏次数'),
    (PLAY_LIVE, u'观看直播次数'),
    (SHARE_LIVE, u'分享直播次数'),
    (BEGIN_LIVE, u'首次开启直播'),
    (JOIN_COLLECT, u'参加游玩视频征集活动次数'),
)

TASK_STATUS = (
    (UNFINISHED, u'未完成'),
    (FINISHED, u'已完成'),
    (RECEIVED, u'已领取'),
)

TASK_PLATFORMS = (
    (ALL_PLATFORM, u'全部'),
    (ANDROID_ONLY, u'Android'),
    (IOS_ONLY, u'IOS'),
)

class Task(BaseModel):
    task_id = pw.PrimaryKeyField(verbose_name='任务ID')
    title = pw.CharField(max_length=64, verbose_name='任务标题')
    description = pw.CharField(max_length=255, verbose_name='任务描述')
    image = pw.CharField(max_length=255, verbose_name='图片')
    task_type = pw.IntegerField(choices=TASK_TYPE, verbose_name='任务类型')
    action = pw.IntegerField(choices=TASK_ACTION, verbose_name='任务条件')
    activity_id = pw.CharField(max_length=64, verbose_name='活动ID')
    game_id = pw.CharField(max_length=64, default='', verbose_name='游戏ID')
    num = pw.IntegerField(default=1, verbose_name='条件数值')
    product_id = pw.IntegerField(verbose_name='奖励物品ID')
    product_num = pw.IntegerField(verbose_name='奖励物品数量')
    task_platform = pw.IntegerField(choices=TASK_PLATFORMS, verbose_name='任务平台')

    class Meta:
        db_table = 'task'

    @classmethod
    @util.cached_object(TASK_KEY)
    def _load_all_tasks(cls):
        tasks = list(cls.select())
        tasks = [model_to_dict(task) for task in tasks]
        return tasks

    @classmethod
    def get_all_tasks(cls):
        tasks = Redis.get(TASK_KEY)
        if not tasks:
            tasks = cls._load_all_tasks()
        else:
            tasks = cjson.loads(tasks)

        tasks = [dict_to_model(Task, task) for task in tasks]
        return tasks

    @classmethod
    def get_task(cls, task_id):
        tasks = filter(lambda x: x.task_id == task_id, cls.get_all_tasks())
        return tasks[0] if tasks else None

    @classmethod
    def get_novice_tasks(cls):
        tasks = filter(lambda x: x.task_type == NOVICE_TASK, cls.get_all_tasks())
        return tasks

    @classmethod
    def get_daily_tasks(cls):
        tasks = filter(lambda x: x.task_type == DAILY_TASK, cls.get_all_tasks())
        return tasks

    @classmethod
    def get_game_tasks(cls):
        tasks = filter(lambda x: x.task_type == GAME_TASK, cls.get_all_tasks())
        return tasks

    @classmethod
    def get_activity_tasks(cls):
        tasks = filter(lambda x: x.task_type == ACTIVITY_TASK, cls.get_all_tasks())
        return tasks

    def format(self):
        data = model_to_dict(self)
        image = self.image
        if self.game_id and not image:
            game = Game.get_one(self.game_id, check_online=False)
            image = game and game.icon

        data['image'] = urljoin(app.config.get("MEDIA_URL"), image)
        return data


class UserTask(BaseModel):
    user_id = pw.CharField(max_length=64, verbose_name='用户ID')
    task_id = pw.IntegerField(verbose_name='任务ID')
    task_type = pw.IntegerField(choices=TASK_TYPE, verbose_name='任务类型')
    action = pw.IntegerField(choices=TASK_ACTION, verbose_name='任务条件')
    finish_num = pw.IntegerField(default=0, verbose_name='已完成数值')
    task_status = pw.IntegerField(choices=TASK_STATUS, default=1, verbose_name='任务状态')

    class Meta:
        db_table = 'user_task'
        primary_key = pw.CompositeKey('user_id', 'task_id')

    @classmethod
    @util.cached_object(lambda cls, user_id: USER_TASK_KEY % (user_id))
    def _load_user_tasks(cls, user_id):
        utasks = list(cls.select().where(UserTask.user_id == user_id))
        utasks = [model_to_dict(utask) for utask in utasks]
        return utasks

    @classmethod
    def get_user_tasks(cls, user_id):
        key = USER_TASK_KEY % (user_id)
        utasks = Redis.get(key)
        if not utasks:
            utasks = cls._load_user_tasks(user_id)
        else:
            utasks = cjson.loads(utasks)

        utasks = [dict_to_model(UserTask, utask) for utask in utasks]
        return utasks

    @classmethod
    def get_user_task(cls, user_id, task_id):
        user_tasks = filter(lambda x: x.task_id == task_id, cls.get_user_tasks(user_id))
        return user_tasks[0] if user_tasks else None

    @classmethod
    def get_novice_tasks(cls, user_id):
        user_tasks = filter(lambda x: x.task_type == NOVICE_TASK and x.task_status != RECEIVED,
                            cls.get_user_tasks(user_id))
        return user_tasks

    @classmethod
    def get_daily_tasks(cls, user_id):
        user_tasks = filter(lambda x: x.task_type == DAILY_TASK, cls.get_user_tasks(user_id))
        return user_tasks

    @classmethod
    def get_game_tasks(cls, user_id):
        user_tasks = filter(lambda x: x.task_type == GAME_TASK, cls.get_user_tasks(user_id))
        return user_tasks

    @classmethod
    def get_activity_tasks(cls, user_id):
        user_tasks = filter(lambda x: x.task_type == ACTIVITY_TASK, cls.get_user_tasks(user_id))
        return user_tasks

    @classmethod
    def create_and_init_user_tasks(cls, user_id):
        # 删除任务已被移除的用户任务
        cls.delete_removed_tasks(user_id)

        uc = UserCredit.get_or_create_user_credit(user_id)
        # 刷新每日任务
        if uc.task_at.date() < datetime.date.today():
            UserTask.refresh_daily_tasks(user_id)
        # 如果没有活动任务创建活动任务
        # if not UserTask.get_activity_tasks(user_id):
        # 检查并更新活动任务
        UserTask.init_tasks(user_id, ACTIVITY_TASK)
        # 检查并更新新手任务
        UserTask.init_tasks(user_id, NOVICE_TASK)
        # 检查并更新游戏任务
        UserTask.init_tasks(user_id, GAME_TASK)

    @classmethod
    def init_tasks(cls, user_id, task_type=None):
        _tasks = []
        if task_type == ACTIVITY_TASK:
            for task in Task.get_activity_tasks():
                # 去重
                exists = cls.select().where(cls.user_id == user_id, cls.task_id ==task.task_id).count()
                if exists:
                    continue
                tmp = dict(user_id=user_id, task_id=task.task_id,
                           task_type=task.task_type, action=task.action)
                _tasks.append(tmp)
            if _tasks:
                UserTask.insert_many(_tasks).execute()
            key = USER_TASK_KEY % (user_id)
            Redis.delete(key)
            return

        if task_type == NOVICE_TASK:
            for task in Task.get_novice_tasks():
                # 去重
                exists = cls.select().where(cls.user_id == user_id, cls.task_id ==task.task_id).count()
                if exists:
                    continue
                tmp = dict(user_id=user_id, task_id=task.task_id,
                           task_type=task.task_type, action=task.action)
                _tasks.append(tmp)
            if _tasks:
                UserTask.insert_many(_tasks).execute()
            key = USER_TASK_KEY % (user_id)
            Redis.delete(key)
            return

        if task_type == GAME_TASK:
            for task in Task.get_game_tasks():
                # 去重
                exists = cls.select().where(cls.user_id == user_id, cls.task_id ==task.task_id).count()
                if exists:
                    continue
                tmp = dict(user_id=user_id, task_id=task.task_id,
                           task_type=task.task_type, action=task.action)
                _tasks.append(tmp)
            if _tasks:
                UserTask.insert_many(_tasks).execute()
            key = USER_TASK_KEY % (user_id)
            Redis.delete(key)
            return

        for task in Task.get_all_tasks():
            tmp = dict(user_id=user_id, task_id=task.task_id,
                       task_type=task.task_type, action=task.action)
            # 每日签到任务自动完成
            if task.action == DAILY_SIGNIN:
                tmp['task_status'] = FINISHED
                tmp['finish_num'] = 1
            _tasks.append(tmp)

        if _tasks:
            UserTask.insert_many(_tasks).execute()

    @classmethod
    def refresh_daily_tasks(cls, user_id):
        _tasks = []
        for task in Task.get_daily_tasks():
            tmp = dict(user_id=user_id, task_id=task.task_id,
                       task_type=task.task_type, action=task.action)
            # 每日签到任务自动完成
            if task.action == DAILY_SIGNIN:
                tmp['task_status'] = FINISHED
                tmp['finish_num'] = 1
            _tasks.append(tmp)

        with MYDB.atomic():
            # 删除旧的每日任务
            cls.delete().where(UserTask.user_id == user_id, UserTask.task_type == 2).execute()
            # 增加新的每日任务
            if _tasks:
                UserTask.insert_many(_tasks).execute()
            # 修改任务刷新时间
            UserCredit.update(
                task_at=datetime.datetime.now()
            ).where(UserCredit.user_id == user_id).execute()

        key = USER_TASK_KEY % (user_id)
        Redis.delete(key)

    @classmethod
    def check_user_tasks(cls, user_id, action, action_num=1, game_id=None, activity_id=None):
        user_tasks = filter(lambda x: x.action == action and x.task_status == UNFINISHED,
                            cls.get_user_tasks(user_id))

        for utask in user_tasks:
            task = Task.get(Task.task_id == utask.task_id)
            # 如果基本任务已被删除，则删除用户任务
            if not task:
                utask.delete_instance()
                continue

            if task.task_type == GAME_TASK and task.game_id != game_id:
                continue

            # 如果任务类型为活动任务且任务的活动ID已配置，则需要检查game_id是否在活动的game_id下
            if task.task_type == ACTIVITY_TASK and task.activity_id:
                # 如果活动ID不一致，则不计任务
                if activity_id != str(task.activity_id):
                    continue
                gids = GameActivity.game_activity_ids(task.activity_id)
                # 如果游戏ID不在活动范围内，则不完成任务
                if gids and game_id not in gids:
                    continue

            utask.finish_num += action_num
            # 任务完成
            if utask.finish_num >= task.num:
                utask.task_status = FINISHED
                # 发送任务完成消息到队列
                channel = User.USER_ASYNC_MSG % ({'uid': str(user_id)})
                msg = dict(obj_type='Task', obj_id=utask.task_id, count=1)
                MRedis.publish(channel, json.dumps(msg))

            utask.save()
        # 删除用户任务缓存
        if len(user_tasks) > 0:
            key = USER_TASK_KEY % (user_id)
            Redis.delete(key)

    @classmethod
    def delete_removed_tasks(cls, user_id):
        # 删除任务已被移除的用户任务
        need_to_delete = False
        for utask in cls.get_user_tasks(user_id):
            if Task.get_task(utask.task_id) is None:
                utask.delete_instance()
                need_to_delete = True

        if need_to_delete:
            key = USER_TASK_KEY % (user_id)
            Redis.delete(key)

    def format(self):
        data = model_to_dict(self)
        task = Task.get_task(self.task_id)
        data.update(task.format())
        if self.task_status == FINISHED:
            data['btn_desc'] = '领取' if task.action != DAILY_SIGNIN else '签到'
        elif self.task_status == RECEIVED:
            data['btn_desc'] = '已领取'
        else:
            data['btn_desc'] = '未完成' if task.task_type != GAME_TASK else '下载'
        return data

    @property
    def is_finished(self):
        return self.task_status == FINISHED

    def receive_rewards(self):
        if not self.is_finished:
            return []

        task = Task.get(Task.task_id == self.task_id)
        key = USER_TASK_KEY % (self.user_id)
        # 如果基本任务已被删除，则删除用户任务
        if not task:
            self.delete_instance()
            Redis.delete(key)
            return []

        product = Product.get(Product.product_id == task.product_id)
        rewards = []
        with MYDB.atomic():
            self.task_status = RECEIVED
            self.save()
            if product.add_product2user(self.user_id, task.product_num, const.TASK):
                rewards.append(dict(name=product.product_name, num=task.product_num))

        Redis.delete(key)
        return rewards
