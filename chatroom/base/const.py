# -*- coding: utf8 -*-

# friendship状态
WAIT = 0
AGREE = 1
REFUSE = 2
BLACK = 3
DELETE = 4

# 发送邮件主题
VERIFY = '请激活您的pigroom超级聊天室账号'
INTERFACE = 'account/accountActivation?loginName={name}&code={code}&&callback={callback}'
CALLBACK = 'https://www.baidu.com'

# 用户状态
WAITVERIFY = 0
REGISTERSUCCESS = 1
BEBENED = 2
OVERDUE = 3

OFFLINE = WAITVERIFY
