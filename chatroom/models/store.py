# -*- coding: utf8 -*-
from datetime import datetime
from playhouse.shortcuts import model_to_dict, dict_to_model
from urlparse import urljoin
from wanx import app
from wanx.base import const, util
from wanx.base.xredis import Redis
from wanx.models import BaseModel
from wanx.models.product import Product

import cPickle as cjson
import peewee as pw
import json


ALL_STORE_KEY = 'store:all'
STORE_ITEM_KEY = 'store_item:%(store_id)s'

LOTTERY = 1
EXCHANGE = 2

STORE_TYPE = (
    (LOTTERY, u'抽奖区'),
    (EXCHANGE, u'兑换区')
)

CREDIT_TYPE = (
    (const.SALE_GEM, u'游票价格'),
    (const.SALE_GOLD, u'游米价格'),
)

STORE_STATUS = (
    (1, u'进行中'),
    (2, u'暂停'),
    (3, u'结束'),
)

STATUS = (
    (const.ORDER_NEED_DRAW, u'未领取'),
    (const.ORDER_FINISHED, u'已到帐'),
    (const.ORDER_IN_HAND, u'营销平台处理中'),
    (const.ORDER_FAILED, u'发送失败'),
)

LIVE_GIFT = 1
LIVE_REDPACKET = 2
LIVE_ACTIVITY_TYPE = (
    (LIVE_GIFT, u'直播间送礼'),
    (LIVE_REDPACKET, u'直播间红包'),
)


class Store(BaseModel):
    store_id = pw.PrimaryKeyField(verbose_name='商店ID')
    store_type = pw.IntegerField(choices=STORE_TYPE, verbose_name='商店类型')
    title = pw.CharField(max_length=512, verbose_name='商店描述')
    credit_type = pw.IntegerField(choices=CREDIT_TYPE, verbose_name='参与价格类型')
    credit_value = pw.IntegerField(default=0, verbose_name='参与价格数值')
    status = pw.IntegerField(choices=STORE_STATUS, verbose_name='状态')
    begin_at = pw.DateTimeField(formats='%Y-%m-%d %H:%M:%S', verbose_name='开始时间')
    expire_at = pw.DateTimeField(formats='%Y-%m-%d %H:%M:%S', verbose_name='结束时间')
    action = pw.CharField(default='', max_length=512, verbose_name='跳转链接')
    order = pw.IntegerField(verbose_name='显示顺序')
    campaign_id = pw.CharField(default='', max_length=512, verbose_name='营销平台活动ID')
    resource_campaign_id = pw.CharField(default='', max_length=512, verbose_name='营销平台流量话费发放活动ID')
    share_image = pw.CharField(default='', max_length=512, verbose_name='分享图片')
    share_title = pw.CharField(default='', max_length=512, verbose_name='分享标题')

    class Meta:
        db_table = 'store'

    @classmethod
    def all_stores_for_admin(cls):
        stores = list(cls.select())

        store_list = []
        for s in stores:
            type_desc = util.get_choices_desc(STORE_TYPE, s.store_type)
            value = u'【%s(%s)】%s' % (type_desc, s.store_id, s.title)
            store_list.append((s.store_id, value))

        return store_list

    @classmethod
    def get_all_stores(cls):
        stores = Redis.get(ALL_STORE_KEY)
        if stores:
            stores = cjson.loads(stores)
            stores = [dict_to_model(Store, s) for s in stores]
        else:
            stores = list(cls.select())
            _stores = [model_to_dict(s) for s in stores]
            Redis.setex(ALL_STORE_KEY, 86400, cjson.dumps(_stores, 2))

        return stores

    @classmethod
    def get_store(cls, store_id):
        stores = filter(lambda x: x.store_id == int(store_id), cls.get_all_stores())
        return stores[0] if stores else None

    @classmethod
    def get_lotteries(cls):
        lotteries = filter(lambda x: x.store_type == LOTTERY and x.online(), cls.get_all_stores())
        return sorted(lotteries, key=lambda x: x.order)

    @classmethod
    def get_exchanges(cls):
        exchanges = filter(lambda x: x.store_type == EXCHANGE and x.online(), cls.get_all_stores())
        return sorted(exchanges, key=lambda x: x.order)

    def format(self):
        _share_uri = '/page/html/sharelottery.html?store_id=%s' % (self.store_id)
        share_url = urljoin(app.config.get('SHARE_URL'), _share_uri)
        share_image = ''
        if self.share_image:
            share_image = urljoin(app.config.get("MEDIA_URL"), self.share_image)

        data = {
            'store_id': self.store_id,
            'title': self.title,
            'credit_type': self.credit_type,
            'credit_value': self.credit_value,
            'status': self.status,
            'action': self.action,
            'share_url': share_url,
            'share_image': share_image,
            'share_title': self.share_title,
            'expire_at': util.datetime2timestamp(self.expire_at)
        }
        return data

    def online(self):
        if self.status == 3:
            return False

        # 还未到上线时间或已到下线时间
        if self.begin_at > datetime.now() or self.expire_at < datetime.now():
            return False

        return True

    def pause(self):
        if self.online() and self.status == 2:
            return True

        return False


class StoreItem(BaseModel):
    item_id = pw.PrimaryKeyField(verbose_name='条目ID')
    store_id = pw.IntegerField(verbose_name='商店ID')
    product_id = pw.IntegerField(verbose_name='物品ID')
    product_num = pw.IntegerField(verbose_name='物品数量')
    title = pw.CharField(max_length=512, verbose_name='商品描述')
    credit_type = pw.IntegerField(choices=CREDIT_TYPE, verbose_name='价格类型')
    credit_value = pw.IntegerField(default=0, verbose_name='价格数值')
    total_num = pw.IntegerField(verbose_name='总库存(份)')
    use_num = pw.IntegerField(verbose_name='消耗数量(份)')
    left_num = pw.IntegerField(verbose_name='剩余库存(份)')
    order = pw.IntegerField(verbose_name='显示顺序')
    identity = pw.CharField(default='', max_length=512, verbose_name='营销平台奖项标识')

    class Meta:
        db_table = 'store_item'

    @classmethod
    def get_store_items(cls, store_id):
        key = STORE_ITEM_KEY % ({'store_id': store_id})
        items = Redis.get(key)
        if items:
            items = cjson.loads(items)
            items = [dict_to_model(StoreItem, i) for i in items]
        else:
            items = list(cls.select().where(cls.store_id == int(store_id)))
            _items = [model_to_dict(i) for i in items]
            Redis.setex(key, 86400, cjson.dumps(_items, 2))

        return sorted(items, key=lambda x: x.order)

    @classmethod
    def get_store_item(cls, store_id, item_id):
        items = filter(lambda x: x.item_id == int(item_id), cls.get_store_items(store_id))
        return items[0] if items else None

    @classmethod
    def get_item_by_identity(cls, store_id, identity):
        if not identity:
            return None

        items = filter(lambda x: x.store_id == int(store_id) and x.identity == identity,
                       cls.get_store_items(store_id))
        return items[0] if items else None

    def format(self):
        product = Product.get_product(self.product_id)
        data = {
            'item_id': self.item_id,
            'title': self.title,
            'credit_type': self.credit_type,
            'credit_value': self.credit_value,
            'product': product.format(),
            'product_num': self.product_num,
            'left_num': self.left_num,
            'use_num': self.use_num
        }
        return data

    def save(self, *args, **kwargs):
        ret = super(StoreItem, self).save(*args, **kwargs)
        key = STORE_ITEM_KEY % ({'store_id': self.store_id})
        Redis.delete(key)
        return ret


class UserOrder(BaseModel):
    order_id = pw.PrimaryKeyField(verbose_name='订单ID')
    user_id = pw.CharField(max_length=64, verbose_name='用户ID')
    item_id = pw.IntegerField(verbose_name='条目ID')
    store_id = pw.IntegerField(verbose_name='商店ID')
    store_type = pw.IntegerField(choices=STORE_TYPE, verbose_name='商店类型')
    campaign_id = pw.CharField(default='', max_length=512, verbose_name='营销平台活动ID')
    title = pw.CharField(default=512, verbose_name='商品描述')
    product_id = pw.IntegerField(verbose_name='物品ID')
    product_num = pw.IntegerField(verbose_name='物品数量')
    status = pw.IntegerField(choices=STATUS, verbose_name='状态')
    result = pw.CharField(default='', max_length=1024, verbose_name='营销平台结果')
    recid = pw.CharField(null=True, max_length=128, verbose_name='营销平台订单号')

    class Meta:
        db_table = 'user_order'

    @classmethod
    def get_order(cls, order_id):
        try:
            order = cls.get(cls.order_id == int(order_id))
        except cls.DoesNotExist:
            order = None

        return order

    @classmethod
    def get_user_store_orders(cls, user_id, store_id, page, pagesize):
        orders = list(cls.select().where(
            cls.user_id == user_id,
            cls.store_id == int(store_id)
        ).order_by(cls.create_at.desc()).paginate(page, pagesize))
        return orders

    @classmethod
    def get_orders_in_hand(cls):
        orders = list(cls.select().where(
            cls.campaign_id != '',
            cls.status == const.ORDER_IN_HAND,
            ~(cls.recid >> None)
        ))
        return orders

    def format(self):
        product = Product.get_product(self.product_id)
        result = json.loads(self.result) if self.result else None
        rid = result['id'] if result and 'id' in result else None
        code = result['giftCode'] if result and 'giftCode' in result else None
        name = result['name'] if result and 'name' in result else None
        data = {
            'order_id': self.order_id,
            'title': self.title,
            'product': product and product.format(),
            'status': self.status,
            'create_at': util.datetime2timestamp(self.create_at),
            'result': {'code': code, 'name': name, 'rid': rid}
        }
        return data


class UserOrderAddress(BaseModel):
    order_id = pw.IntegerField(verbose_name='订单ID')
    user_id = pw.CharField(max_length=64, verbose_name='用户ID')
    name = pw.CharField(max_length=64, verbose_name='真实姓名')
    phone = pw.CharField(max_length=64, verbose_name='手机号')
    id_card = pw.CharField(max_length=64, verbose_name='身份证')
    address = pw.CharField(max_length=1024, verbose_name='收货地址')

    class Meta:
        db_table = 'user_order_address'


class UserLiveOrder(BaseModel):
    order_id = pw.PrimaryKeyField(verbose_name='订单ID')
    user_id = pw.CharField(max_length=64, verbose_name='用户ID')
    item_id = pw.CharField(max_length=64, verbose_name='条目ID')
    activity_id = pw.CharField(max_length=64, verbose_name='商店ID')
    activity_type = pw.IntegerField(choices=LIVE_ACTIVITY_TYPE, verbose_name='商店类型')
    campaign_id = pw.CharField(default='', max_length=512, verbose_name='营销平台活动ID')
    title = pw.CharField(default=512, verbose_name='商品描述')
    product_id = pw.IntegerField(verbose_name='物品ID')
    product_num = pw.IntegerField(verbose_name='物品数量')
    status = pw.IntegerField(choices=STATUS, verbose_name='状态')
    result = pw.CharField(default='', max_length=1024, verbose_name='营销平台结果')
    recid = pw.CharField(null=True, max_length=128, verbose_name='营销平台订单号')

    class Meta:
        db_table = 'user_live_order'

