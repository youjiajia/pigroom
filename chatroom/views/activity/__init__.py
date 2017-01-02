# -*- coding: utf8 -*-
"""
=======================
接口中的对象属性定义
=======================

-------------------------------
活动视频（ActivityVideo）:
-------------------------------
==================     =========  =====================
属性名                  类型       说明
==================     =========  =====================
activity_video         string     参赛视频唯一标识
activity_id            string     视频描述
video_id               string     视频唯一标识
cover                  url        视频封面
author                 User       视频作者
like_count             bool       被点赞次数
create_at              float       创建时间
comment_count          int        评论数量
vv                     int        播放次数
duration               int        时长（秒）
url                    url        视频播放url
vote                   int        投票数
is_voted               bool       是否已投票
==================     =========  =====================

-------------------------------
评论（Comment）:
-------------------------------
==================     =========  =====================
属性名                  类型       说明
==================     =========  =====================
comment_id             string     评论唯一标识
activity_id            string     视频ID
author                 User       评论作者
content                string     评论内容
create_at              float      评论时间
like                   int        被点赞次数
liked                  int        当前用户是否已点赞
==================     =========  =====================


-------------------------------
活动游戏（GameActivity）:
-------------------------------
==================     =========  =====================
属性名                  类型       说明
==================     =========  =====================
game_id                string     游戏ID
icon                   string     游戏icon
name                   string     游戏名称
is_download            bool       是否可下载
package_id             string     游戏包id
==================     =========  =====================



-------------------------------
活动配置（ActivityConfig）:
-------------------------------
==================     =========  =====================
属性名                  类型       说明
==================     =========  =====================
activity_id            string     活动ID
description            string     活动描述(app内使用)
vote_text              string     投票按钮显示文字
voted_text             string     投票按钮显示文字
activity_url           string     活动url
sort                   string     活动排序依据
share_banner           string     活动分享页广告
share_description      string     活动分享页活动介绍
share_vote_text        string     活动分享页投票按钮文字
share_voted_text       string     活动分享页已投票按钮文字
activity_rule          string     活动规则
status                 string     活动状态
activity_banner        string     活动页banner
button_join            string     我要参加按钮')
rule_image             string     游玩大礼图片
button_lp              string     拉票按钮
button_tp              string     投票按钮
button_tp_link         string     投票按钮链接
==================     =========  =====================
"""
