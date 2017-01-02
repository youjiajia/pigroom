# -*- coding: utf8 -*-
from wanx.base import util, const
from wanx.models import BaseModel

import datetime
import peewee as pw


TRADE_ACTION = (
    (const.TASK, '任务奖励'),
    (const.GIFT, '购买礼物'),
    (const.EXCHANGE, '兑换物品'),
    (const.LOTTERY, '抽奖消费'),
    (const.LOTTERY_REWAED, '抽奖'),
)


class UserCredit(BaseModel):
    user_id = pw.CharField(max_length=64, primary_key=True, verbose_name='用户ID')
    gem = pw.IntegerField(default=0, verbose_name='游票数')
    gold = pw.IntegerField(default=0, verbose_name='游米数')
    task_at = pw.DateTimeField(formats='%Y-%m-%d %H:%M:%S', verbose_name='任务更新时间')
    gift_at = pw.DateTimeField(formats='%Y-%m-%d %H:%M:%S', verbose_name='免费礼物更新时间')

    class Meta:
        db_table = 'user_credit'

    @classmethod
    def get_or_create_user_credit(cls, user_id):
        uc, created = cls.get_or_create(user_id=user_id,
                                        defaults={
                                            'task_at': datetime.datetime.now(),
                                            'gift_at': datetime.datetime.now()
                                        })
        if created:
            # 初始化用户任务
            from wanx.models.task import UserTask
            UserTask.init_tasks(user_id)
            # 初始化免费礼物
            from wanx.models.product import UserProduct
            UserProduct.refresh_daily_free_gifts(user_id)

        return uc

    def _change_gem(self, num, action):
        self.gem += num
        self.save()
        # 增加交易记录
        UserGemLog.create(user_id=self.user_id, gem=num, action=action)

    def add_gem(self, num, action):
        self. _change_gem(num, action)if num > 0 else None

    def reduce_gem(self, num, action):
        self. _change_gem(-num, action) if num > 0 else None

    def _change_gold(self, num, action):
        self.gold += num
        self.save()
        # 增加交易记录
        UserGoldLog.create(user_id=self.user_id, gold=num, action=action)

    def add_gold(self, num, action):
        self. _change_gold(num, action) if num > 0 else None

    def reduce_gold(self, num, action):
        self. _change_gold(-num, action) if num > 0 else None


class UserGemLog(BaseModel):
    user_id = pw.CharField(max_length=64, verbose_name='用户ID')
    gem = pw.IntegerField(default=0, verbose_name='交易游票数')
    action = pw.IntegerField(choices=TRADE_ACTION, verbose_name='交易描述')

    class Meta:
        db_table = 'user_gem_log'
        indexes = (
            (('user_id', 'create_at'), False),
        )

    @classmethod
    def get_user_logs(cls, user_id, page, pagesize):
        logs = list(cls.select().where(
            cls.user_id == user_id
        ).order_by(cls.create_at.desc()).paginate(page, pagesize))
        return logs

    def format(self):
        data = {
            'gem': self.gem,
            'action': self.action,
            'desc': util.get_choices_desc(TRADE_ACTION, self.action),
            'create_at': util.datetime2timestamp(self.create_at)
        }
        return data


class UserGoldLog(BaseModel):
    user_id = pw.CharField(max_length=64, verbose_name='用户ID')
    gold = pw.IntegerField(default=0, verbose_name='交易游米数')
    action = pw.IntegerField(choices=TRADE_ACTION, verbose_name='交易描述')

    class Meta:
        db_table = 'user_gold_log'
        indexes = (
            (('user_id', 'create_at'), False),
        )

    @classmethod
    def get_user_logs(cls, user_id, page, pagesize):
        logs = list(cls.select().where(
            cls.user_id == user_id
        ).order_by(cls.create_at.desc()).paginate(page, pagesize))
        return logs

    def format(self):
        data = {
            'gold': self.gold,
            'action': self.action,
            'desc': util.get_choices_desc(TRADE_ACTION, self.action),
            'create_at': util.datetime2timestamp(self.create_at)
        }
        return data
