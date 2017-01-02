# -*- coding: utf8 -*-

# 密码长度
PWD_HASH_LEN = 32

# 默认密码, '0123456789'
DEFAULT_PWD = 'e643545efd10404fa3ed7a7e2e62e71e70ff987b3dc88cb975f98f480d6b1a15'

# 默认salt, '0' * 16
DEFAULT_SALT = '0000000000000000'

# Token过期时间
TOKEN_EXPIRE = 3600 * 24 * 15

# 消息队列过期时间
MSG_LIST_EXPIRE = 3600 * 24 * 7

# 第三方登录平台标识和存储标识
PARTNER = dict(
    migu='migu',
    csdk='migu',
    weixin='weixin',
    qq='qq'
)

# 用户允许更改信息
USER_ALLOWED_MODIFY = {
    "nickname": unicode,
    "phone": str,
    "birthday": int,
    "email": str,
    "gender": int,
    "signature": unicode,
    "announcement": unicode,
}

# 0: 在线, 1: 下线, 2: 测试, 3:精选, 4:上传中
ONLINE = 0
OFFLINE = 1
UNDER_TEST = 2
ELITE = 3
UPLOADING = 4

# 用户中心
CENTER_ACCOUNT_PHONE = '3'
CENTER_ACCOUNT_INDIV = '1'
CENTER_ACCOUNT_SOURCEID = '206014'
CENTER_ACCOUNT_APPID = '20601401'


# 最新视频和游戏的全部视频过滤(条件:大于等于, 单位:秒)
DURATION = 30
# 人气视频规则条件
POPULAR_VIDEO = {
    "time_range": 7 * 24 * 60 * 60,
    "max_video_num": 30
}

# 推荐关注用户数量
RECOMMEND_ATTENTION = 15
# 推荐关注的用户从多少里取出来
RECOMMEND_ATTENTION_POOL = 100

# 活动分类对应送出流量 (单位:M)
TRAFFIC = dict(
    first_login=150,
    video_share=150
)
# 活动分类对应数量
TRAFFIC_CATEGORY_NUM = dict(
    first_login=30000,
    video_share=24000
)
# 流量送出指定分享平台
PLATFORM_SHARE = ['qq', 'weixin', 'qzone', 'moments']
# 流量发放状态 0:充值成功 1:充值失败 2:正在处理 3:用户流量到账成功  4:用户流量到账失败  5:流量充值正在处理中
TRAFFIC_SUCCESS = 0
TRAFFIC_FAIL = 1
TRAFFIC_PROCESS = 2
TRAFFIC_RECEIVED_SUCCESS = 3
TRAFFIC_RECEIVED_FAIL = 4
TRAFFIC_RECEIVED_PROCESS = 5
# 给自由充平台返回的xml success_xml:成功  fail_xml:失败
SUCCESS_XML = '''<?xml version="1.0" encoding="utf-8"?>
                    <RESPONSE>
                        <ACTION>MeberShipMessage</ACTION>
                        <retCode>0</retCode>
                        <retMsg>接收成功</retMsg>
                    </RESPONSE>
                '''
FAIL_XML = '''<?xml version="1.0" encoding="utf-8"?>
                    <RESPONSE>
                        <ACTION>MeberShipMessage</ACTION>
                        <retCode>-1</retCode>
                        <retMsg>接收失败</retMsg>
                    </RESPONSE>
                '''
# 活动 begin: 开始 pause:暂停 end:结束
ACTIVITY_BEGIN = 'begin'
ACTIVITY_PAUSE = 'pause'
ACTIVITY_END = 'end'

FROM_LIVE = 1  # 直播
FROM_RECORD = 2  # 录播

SALE_GEM = 1  # 游票
SALE_GOLD = 2  # 游米
DAILY_FREE = 3  # 每日免费

TASK = 1
GIFT = 2
EXCHANGE = 3
LOTTERY = 4
LOTTERY_REWAED = 5

ORDER_NEED_DRAW = 1
ORDER_IN_HAND = 2
ORDER_FINISHED = 3
ORDER_FAILED = 4

WHITELIST_GROUP = 'whitelist'
BLACKLIST_GROUP = 'blacklist'

# banner 兼容老版本
BANNER_VERSION = 57
