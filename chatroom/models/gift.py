# -*- coding: utf8 -*-
from playhouse.shortcuts import model_to_dict, dict_to_model
from redis import exceptions
from wanx.models import BaseModel
from wanx.base.xredis import Redis
from wanx.base.xmysql import MYDB
from wanx.base import error, util, const
from wanx.models.credit import UserCredit
from wanx.models.product import Product, UserProduct
from wanx.models.user import User

import cPickle as cjson
import peewee as pw
from datetime import datetime


ONSALE_GIFT_KEY = 'gift:onsale'
VIDEO_GIFT_KEY = 'gift:video:%s'
TOP_SENDER_KEY = 'gift:top_senders:%s'
USER_TOTAL_GOLD = 'user:total:gold:%(uid)s'

CREDIT_TYPE = (
    (const.SALE_GEM, u'游票价格'),
    (const.SALE_GOLD, u'游米价格'),
    (const.DAILY_FREE, u'每日免费次数'),
)

GIFT_FROM = (
    (const.FROM_LIVE, '直播'),
    (const.FROM_RECORD, '录播'),
)


class Gift(BaseModel):
    gift_id = pw.PrimaryKeyField(verbose_name='礼物ID')
    product_id = pw.IntegerField(verbose_name='物品ID')
    credit_type = pw.IntegerField(choices=CREDIT_TYPE, verbose_name='价格类型')
    credit_value = pw.IntegerField(verbose_name='价格数值')
    on_sale = pw.BooleanField(default=True, verbose_name='是否在售')

    class Meta:
        db_table = 'gift'
        constraints = [pw.Check('credit_value > 0')]

    @classmethod
    @util.cached_object(ONSALE_GIFT_KEY)
    def _load_onsale_gifts(cls):
        gifts = list(cls.select().where(Gift.on_sale == True))
        gifts = [model_to_dict(gf) for gf in gifts]
        return gifts

    @classmethod
    def get_onsale_gifts(cls):
        gifts = Redis.get(ONSALE_GIFT_KEY)
        if not gifts:
            gifts = cls._load_onsale_gifts()
        else:
            gifts = cjson.loads(gifts)

        gifts = [dict_to_model(Gift, gf) for gf in gifts]
        return gifts

    @classmethod
    def get_free_gifts(cls):
        gifts = filter(lambda x: x.credit_type == const.DAILY_FREE, cls.get_onsale_gifts())
        return gifts

    @classmethod
    def get_gift(cls, gift_id):
        gifts = filter(lambda x: x.gift_id == gift_id, cls.get_onsale_gifts())
        return gifts[0] if gifts else None

    def format(self):
        data = model_to_dict(self)
        product = Product.get_product(self.product_id)
        if product:
            data.update(product.format())
        return data

    @property
    def gold_price(self):
        if self.credit_type == const.DAILY_FREE:
            return 100
        elif self.credit_type == const.SALE_GOLD:
            return self.credit_value
        elif self.credit_type == const.SALE_GEM:
            return self.credit_value * 100
        return 0

    def send_to_user(self, from_user, to_user, num, gift_from, from_id):
        if num < 1:
            return error.InvalidArguments

        uc = UserCredit.get_or_create_user_credit(from_user)
        product = Product.get_product(self.product_id)
        if self.credit_type == const.SALE_GOLD:
            total_gold = self.credit_value * num
            if uc.gold < total_gold:
                return error.GiftError('你的游米不足，做任务可获取游米')

            with MYDB.atomic():
                uc.reduce_gold(total_gold, const.GIFT)
                product.add_product2user(to_user, num, const.GIFT)
                UserGiftLog.create(
                    user_id=to_user,
                    from_user=from_user,
                    product_id=self.product_id,
                    credit_type=self.credit_type,
                    credit_value=self.credit_value,
                    num=num,
                    gold_price=self.gold_price * num,
                    gift_from=gift_from,
                    from_id=from_id)
        elif self.credit_type == const.SALE_GEM:
            total_gem = self.credit_value * num
            if uc.gem < total_gem:
                return error.GiftError('你的游票不足')

            with MYDB.atomic():
                uc.reduce_gem(total_gem, const.GIFT)
                product.add_product2user(to_user, num, const.GIFT)
                UserGiftLog.create(
                    user_id=to_user,
                    from_user=from_user,
                    product_id=self.product_id,
                    credit_type=self.credit_type,
                    credit_value=self.credit_value,
                    num=num,
                    gold_price=self.gold_price * num,
                    gift_from=gift_from,
                    from_id=from_id)
        elif self.credit_type == const.DAILY_FREE:
            from_up = UserProduct.get_or_create_user_product(from_user, self.product_id)
            if from_up.gift_free < num:
                return error.GiftError('对不起，您今天的免费礼物已用完')

            with MYDB.atomic():
                from_up.gift_free -= num
                from_up.save()
                product.add_product2user(to_user, num, const.GIFT)
                UserGiftLog.create(
                    user_id=to_user,
                    from_user=from_user,
                    product_id=self.product_id,
                    credit_type=self.credit_type,
                    credit_value=self.credit_value,
                    num=num,
                    gold_price=self.gold_price * num,
                    gift_from=gift_from,
                    from_id=from_id)
        return True


class UserGiftLog(BaseModel):
    user_id = pw.CharField(max_length=64, verbose_name='用户ID')
    from_user = pw.CharField(max_length=64, verbose_name='赠送者ID')
    product_id = pw.IntegerField(verbose_name='物品ID')
    credit_type = pw.IntegerField(choices=CREDIT_TYPE, verbose_name='价格类型')
    credit_value = pw.IntegerField(verbose_name='价格数值')
    num = pw.IntegerField(verbose_name='赠送数量')
    gold_price = pw.IntegerField(verbose_name='折算为游米价格')
    gift_from = pw.IntegerField(choices=GIFT_FROM, verbose_name='礼物来源')
    from_id = pw.CharField(max_length=64, verbose_name='来源ID(视频ID、直播ID)')

    class Meta:
        db_table = 'user_gift_log'

    @classmethod
    @util.cached_zset(lambda cls, video_id: VIDEO_GIFT_KEY % (video_id))
    def _load_video_gifts(cls, video_id):
        gifts = list(cls.select().where(
            UserGiftLog.gift_from == const.FROM_RECORD,
            UserGiftLog.from_id == video_id
        ))
        ret = list()
        for gift in gifts:
            ret.extend([util.datetime2timestamp(gift.create_at), cjson.dumps(gift, 2)])

        return tuple(ret)

    @classmethod
    def get_video_gifts(cls, video_id, maxs=None, pagesize=None):
        key = VIDEO_GIFT_KEY % (video_id)
        if not Redis.exists(key):
            cls._load_video_gifts(video_id)
        try:
            # 不进行分页
            if pagesize is None and maxs is None:
                return Redis.zrevrange(key, 0, -1)
            gifts = Redis.zrevrangebyscore(key, '(%.6f' % (maxs), '-inf', start=0, num=pagesize)
        except exceptions.ResponseError:
            gifts = []

        return [cjson.loads(gf) for gf in gifts]

    @classmethod
    @util.cached_zset(lambda cls, user_id: TOP_SENDER_KEY % (user_id))
    def _load_top_sender_ids(cls, user_id):
        total_gold = pw.fn.Sum(UserGiftLog.gold_price)
        senders = cls.select(
            UserGiftLog.from_user,
            total_gold.alias('gold')
        ).where(UserGiftLog.user_id == user_id).group_by(UserGiftLog.from_user)
        ret = list()
        for sender in senders:
            ret.extend([sender.gold, sender.from_user])

        return tuple(ret)

    @classmethod
    def get_top_sender_ids(cls, user_id, page=None, pagesize=None):
        key = TOP_SENDER_KEY % (user_id)
        if not Redis.exists(key):
            cls._load_top_sender_ids(user_id)

        start = (page - 1) * pagesize if page else 0
        stop = (start + pagesize - 1) if pagesize else -1
        try:
            uids = Redis.zrevrange(key, start, stop, withscores=True)
        except exceptions.ResponseError:
            uids = []

        return list(uids)

    @classmethod
    def get_user_total_gold(cls, uid, begin_at, end_at):
        key = USER_TOTAL_GOLD % ({'uid': uid})
        total_gold = Redis.get(key)
        if not total_gold:
            total_gold = pw.fn.Sum(UserGiftLog.gold_price)
            total_gold = cls.select(
                total_gold.alias('gold')
            ).where(UserGiftLog.user_id == uid,
                    UserGiftLog.gift_from == const.FROM_LIVE,
                    UserGiftLog.create_at > datetime.fromtimestamp(int(begin_at)),
                    UserGiftLog.create_at < datetime.fromtimestamp(int(end_at)))
            total_gold = total_gold.get()
            total_gold = 0 if not total_gold.gold else total_gold.gold
            Redis.setex(key, 86400, total_gold)
        return int(total_gold)

    @classmethod
    def create(cls, **query):
        inst = super(UserGiftLog, cls).create(**query)
        if inst:
            if inst.gift_from == const.FROM_RECORD:
                key = VIDEO_GIFT_KEY % (inst.from_id)
                try:
                    if Redis.exists(key):
                        Redis.zadd(key, util.datetime2timestamp(inst.create_at),
                                   cjson.dumps(inst, 2))
                except exceptions.ResponseError:
                    Redis.delete(key)

            key = TOP_SENDER_KEY % (inst.user_id)
            try:
                if Redis.exists(key):
                    Redis.zincrby(key, inst.gold_price, inst.from_user)
            except exceptions.ResponseError:
                Redis.delete(key)

            if inst.gift_from == const.FROM_LIVE:
                key = USER_TOTAL_GOLD % ({'uid': inst.user_id})
                Redis.delete(key)

        return inst

    def format(self):
        product = Product.get_product(self.product_id)
        data = {
            'from_user': User.get_one(self.from_user).format(exclude_fields=['is_followed']),
            'product': product and product.format(),
            'num': self.num,
            'create_at': util.datetime2timestamp(self.create_at)
        }
        return data
