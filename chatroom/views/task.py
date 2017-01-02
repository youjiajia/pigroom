# -*- coding: utf8 -*-
from flask import request
from wanx import app
from wanx.base import util, error
from wanx.base.xredis import Redis
from wanx.models.task import UserTask, ACTIVITY_TASK
from wanx.models.credit import UserCredit

import datetime


@app.route('/task/user_tasks', methods=['GET'])
@util.jsonapi(login_required=True)
def user_tasks():
    """获取用户任务列表 (GET&LOGIN)

    :uri: /task/user_tasks
    :param os: APP平台，android, ios, all
    :return: {'daily_tasks': list, 'novice_tasks': list, 'game_tasks': list, 'activity_tasks': list}
    """
    user = request.authed_user
    # 任务创建和更新操作放入UserTask里面以便于用户登录或注册时能够及时调用
    # 由于此API访问需要用户登录，所以不再需要在此步创建和更新任务。
    # 由于跨天的时候，更新任务无法通过refresh_token触发，所以必须给出访问用户任务时触发的功能。
    UserTask.create_and_init_user_tasks(str(user._id))
    pmap = dict(all=1, android=2, ios=3)
    platform = request.values.get('os', 'android')
    pid = pmap.get(platform, 1)
    if pid == 1:
        platforms = pmap.values()
    else:
        platforms = [1, pid]
    platform_filter = lambda x:x['task_platform'] in platforms

    daily_tasks = [utask.format() for utask in UserTask.get_daily_tasks(str(user._id))]
    daily_tasks = filter(platform_filter, daily_tasks)
    novice_tasks = [utask.format() for utask in UserTask.get_novice_tasks(str(user._id))]
    novice_tasks = filter(platform_filter, novice_tasks)
    game_tasks = [utask.format() for utask in UserTask.get_game_tasks(str(user._id))]
    game_tasks = filter(platform_filter, game_tasks)
    activity_tasks = [utask.format() for utask in UserTask.get_activity_tasks(str(user._id))]
    activity_tasks = filter(platform_filter, activity_tasks)
    return {'daily_tasks': daily_tasks, 'novice_tasks': novice_tasks, 'game_tasks': game_tasks,
            'activity_tasks': activity_tasks}


@app.route('/task/receive_reward', methods=['GET', 'POST'])
@util.jsonapi(login_required=True)
def receive_reward():
    """领取任务奖励 (GET|POST&LOGIN)

    :uri: /task/receive_reward
    :param task_id: 任务ID
    :return: {'rewards': list}
    """
    user = request.authed_user
    task_id = request.values.get('task_id', None)
    if not task_id:
        return error.InvalidArguments

    utask = UserTask.get_user_task(str(user._id), int(task_id))
    if not utask:
        return error.TaskError('该任务不存在')

    if not utask.is_finished:
        return error.TaskError('该任务还未完成')

    rewards = []
    key = 'lock:receive_task_reward:%s' % (str(user._id))
    with util.Lockit(Redis, key) as locked:
        if locked:
            return error.TaskError('领取奖励失败')

        rewards = utask.receive_rewards()

    return {'rewards': rewards}
