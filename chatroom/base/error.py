# -*- coding: utf8 -*-

MIGU_ERROR = {
    '0601104102': '手机号码错误',
    '0601104227': '短信验证码校验异常',
    '0601104228': '该手机号请求的短信验证码已达每日上限',
    '0601104229': '账号异常，请联系咪咕客服人员',
    '0601104213': '亲，密码太简单了，验证不通过',
    '0601104209': '密码错误',
    '0601000110': '该用户已存在',
    '0601000105': '验证码发送太频繁，稍后再试',
    '0601000106': '验证码下发超过阈值',
    '0601104214': '亲，密码太简单了，验证不通过',
    '0601104215': '密码错误',  # 该账号是隐式咪咕账号
    '0601104204': '该用户已存在',
    '0601104212': '验证码错误',
    '0601000103': '密码错误',
    '0601104222': '账号未注册',
    '0601104227': '您获取验证码的时间过于频繁，请稍后再试',
    '0601104228': '您今天获取验证码次数已超过上限，请稍后再试',
    '0601104229': '系统繁忙，请稍后再试',
}

MIGU_ERROR_2 = {
    '103000': '成功',
    '103113': '报文格式错误',
    '103114': 'ks过期',
    '103115': 'ks不存在',
    '103116': 'sqn错误',
    '103117': 'mac错误',
    '103121': '平台用户不存在',
    '103122': 'btid不存在',
    '103123': '缓存用户不存在'
}

MARKETING_ERROR = {
    '1100020001': '[营销平台]失败',
    '1100020002': '[营销平台]系统内部错误',
    '1100020003': '[营销平台]参数校验失败',
    '1100020999': '[营销平台]未知错误',
    '1100024003': '[营销平台]活动类型不存在',
    '1100024004': '[营销平台]活动ID不存在',
    '1100024005': '[营销平台]活动服务范围类型不存在',
    '1100024006': '[营销平台]活动服务单位不存在',
    '1100024007': '[营销平台]活动触发事件类型不存在',
    '1100024008': '[营销平台]用户信息错误',
    '1100024009': '[营销平台]适配规则适配失败',
    '1100024010': '[营销平台]不支持的查询方式',
    '1100024401': '[营销平台]超过抢红包次数日上限',
    '1100024402': '[营销平台]红包已抢完',
    '1100024403': '[营销平台]用户已经获得过该红包下奖励',
    '1100024201': '[营销平台]超过抽奖次数日上限',
    '1100024202': '[营销平台]超过抽奖次数周上限',
    '1100024203': '[营销平台]超过抽奖次数月上限',
    '1100024204': '[营销平台]超过抽奖次数总上限',
    '1100024205': '[营销平台]抽奖机会不足',
    '1100024206': '[营销平台]超过获取抽奖机会次数日上限',
    '1100024207': '[营销平台]超过获取抽奖机会次数周上限',
    '1100024208': '[营销平台]超过获取抽奖机会次数月上限',
    '1100024209': '[营销平台]超过获取抽奖机会次数总上限',
    '1100024301': '[营销平台]非有效的F码',
    '1100024302': '[营销平台]F码使用次数达到上限',
    '1100024303': '[营销平台]重复兑换',
    '1100024304': '[营销平台]用户不能分享该F码',
    '1100024305': '[营销平台]F码非法',
    '1100023191': '[营销平台]活动未生效',
    '1100023192': '[营销平台]活动已失效',
    '1100023193': '[营销平台]用户未绑定手机号码',
    '1100023194': '[营销平台]非首次付费',
    '1100023195': '[营销平台]充值金额不适配',
    '1100023196': '[营销平台]分享类型不适配',
    '1100023197': '[营销平台]订购套餐不适配',
    '1100023198': '[营销平台]累计消费金额不适配',
    '1100023199': '[营销平台]升级版本不适配',
    '1100023200': '[营销平台]下载游戏编码不适配',
    '1100023201': '[营销平台]累计下载游戏数量不适配',
    '1100023202': '[营销平台]连续登录次数不适配',
    '1100023203': '[营销平台]累计登录次数不适配',
    '1100023204': '[营销平台]接入门户不适配',
    '1100023205': '[营销平台]超过日签到次数上限',
    '1100023206': '[营销平台]超过周签到次数上限',
    '1100023207': '[营销平台]超过月签到次数上限',
    '1100023208': '[营销平台]超过总签到次数上限',
    '1100023209': '[营销平台]非整点签到',
    '1100023210': '[营销平台]累计签到次数不匹配',
    '1100023211': '[营销平台]连续签到次数不匹配',
    '1100023212': '[营销平台]非目标用户',
    '1100025101': '[营销平台]参数为空的错误码22500',
    '1100025102': '[营销平台]非移动号错误码500000',
    '1100025103': '[营销平台]无效的订单id',
    '1100025103': '[营销平台]订单已经失效'
}


class ApiError(object):

    def __init__(self, name, code, msg):
        self.name = name
        self.errno = code
        self.errmsg = self._errmsg = msg

    def __call__(self, msg=None):
        self.errmsg = msg or self._errmsg
        return self

    def __str__(self):
        return "%s(%d): %s" % (self.name, self.errno, self.errmsg)

RedisFailed = ApiError("RedisFailed", -10000, "缓存操作失败")
InvalidArguments = ApiError("InvalidArguments", -10001, "参数错误")
MissArguments = ApiError("MissArguments", -10002, "缺少参数")
InvalidContent = ApiError("InvalidContent", -10003, "您输入的内容违规")
UserExists = ApiError("UserExists", -10004, "该用户已存在")
UserNotExist = ApiError("UserNotExist", -10005, "该用户不存在")
LoginFailed = ApiError("LoginFailed", -10006, "用户名或密码错误")
SessionExpired = ApiError("SessionExpired", -10007, "用户登录过期")
AuthFailed = ApiError("AuthFailed", -10008, "用户无权限")
AuthRequired = ApiError("AuthRequired", -10009, "需要授权")
GameNotExist = ApiError("GameNotExist", -10010, "该游戏不存在")
VideoNotExist = ApiError("VideoNotExist", -10011, "该视频不存在")
CommentNotExist = ApiError("CommentNotExist", -10012, "该评论不存在")
SendCodeFailed = ApiError("SendCodeFailed", -10013, "发送失败，请稍后再试")
VerifyCodeFailed = ApiError("VerifyCodeFailed", -10014, "短信验证码错误")
RegisterFailed = ApiError("RegisterFailed", -10015, "注册失败，请重试")
UpdatePwdFailed = ApiError("UpdatePwdFailed", -10016, "修改密码失败，请重试")
ResetPwdFailed = ApiError("ResetPwdFailed", -10017, "重置密码失败，请重试")
PasswordFailed = ApiError("PasswordFailed", -10018, "密码错误")
UploadFailed = ApiError("UploadFailed", -10019, "文件上传失败")
NicknameExists = ApiError("NicknameExists", -10020, "昵称已被占用")
NicknameInvalid = ApiError("NicknameInvalid", -10021, "昵称长度不超过4-20个字符，支持汉字、字母、数字的组合")
Md5EncryptInvalid = ApiError("Md5EncryptInvalid", -10022, "Md5加密错误")
UserTrafficInvalid = ApiError("UserTrafficInvalid", -10023, "分享的不是自己的视频, 分享无效")
GameDownloadFailed = ApiError("GameDownloadFailed", -10024, "游戏下载失败")
UserTrafficZero = ApiError('UserTrafficZero', -10025, "亲,我们的奖品已经送完啦,下次要早点来哦!")
UserTrafficExists = ApiError("UserTrafficExists", -10026, "已经分享成功, 再次分享无效")
FollowFailed = ApiError("FollowFailed", -10027, "关注失败，请稍后再试")
SubGameFailed = ApiError("SubGameFailed", -10028, "订阅失败，请稍后再试")
LikeCommentFailed = ApiError("LikeCommentFailed", -10029, "点赞失败，请稍后再试")
FavorVideoFailed = ApiError("FavorVideoFailed", -10030, "收藏视频失败，请稍后再试")
LikeVideoFailed = ApiError("LikeVideoFailed", -10031, "点赞失败，请稍后再试")
TrafficSendFail = ApiError("TrafficSendFail ", -10032, "流量充值失败，请稍后再试")
InvalidRequest = ApiError("InValidRequest", -10033, "非法操作")
ReplyNotExist = ApiError("ReplyNotExist", -10034, "评论回复不存在")
TrafficExists = ApiError("TrafficExists", -10035, "账号已领取过, 不能重复领取")
MiguError = ApiError("MiguError", -10036, "咪咕错误")
LiveError = ApiError("LiveError", -10037, "直播错误")
UserUpgradeFailed = ApiError("UserUpgradeFailed", -10038, "用户升级失败")
TaskError = ApiError("TaskError", -10039, "任务错误")
GiftError = ApiError("GiftError", -10040, "礼物错误")
UserUpgradeFailed = ApiError("UserUpgradeFailed", -10041, "用户升级失败")
ActivityNotExist = ApiError("ActivityNotExist", -10042, "该活动不存在")
ActivityVideoNotExist = ApiError("ActivityVideoNotExist", -10043, "该活动参赛视频不存在")
ActivityVideoExist = ApiError("ActivityVideoExist", -10044, "该活动参赛视频已存在")
StoreError = ApiError("StoreError", -10045, "交易错误")
MarketingError = ApiError("MarketingError", -10046, "营销平台错误")
VoteVideoFailed = ApiError("VoteVideoFailed", -10047, "投票失败，请稍后再试")
ActivityEnd = ApiError("ActivityEndError", -10048, "该活动暂停或已结束")
ReportVideoFailed = ApiError("ReportVideoFailed", -10049, "举报视频失败，请稍后再试")
VideoTopicNotExist = ApiError("VideoTopicNotExist", -10050, "该视频专题不存在")
MteamNotExist = ApiError("MteamNotExist", -10051, "该战队不存在")
GameTopicNotExist = ApiError("GameTopicNotExist", -10052, "该游戏专题不存在")
GameModuleNotExist = ApiError("GameModuleNotExist", -10053, "该游戏模块不存在")
VoteVideoLimited = ApiError("VoteVideoLimited", -10054, "已对该视频投票")
RedPacketError = ApiError("RedPacketNotExist", -10055, "红包活动错误")
LoginRefuse = ApiError("LoginRefuse", -10056, "系统正在升级维护，登录暂不开放，请稍后再试")
PopGameFailed = ApiError("SubGameFailed", -10057, "设置常用游戏失败，请稍后再试")
