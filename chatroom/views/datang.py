# -*- coding: utf8 -*-
from urlparse import urljoin
from flask import request, redirect, jsonify, url_for
from wanx.base.spam import Spam
from wanx.base.xredis import Redis
from wanx.base.media import Media
from wanx.base.guard import Guard
from wanx.models.datang import DaTangVideo
from wanx import app
from wanx.base import util, error, const

import time
import hashlib
import json
import os


@app.route('/datang/videos/<string:vid>', methods=['GET'])
@util.jsonapi(verify=False)
def datang_get_video(vid):
    """获取视频详细信息 (GET)

    :uri: /datang/videos/<string:vid>
    :returns: object
    """
    video = DaTangVideo.get_one(vid, check_online=False)
    if not video:
        return error.VideoNotExist

    return video.format()


@app.route('/datang/videos/new-video', methods=('POST',))
@util.jsonapi(verify=False)
def datang_create_video():
    """创建视频 (POST&LOGIN)

    :uri: /datang/videos/new-video
    :param game_id: 视频所属游戏id
    :param user_id: 用户ID
    :param title: 视频标题
    :param duration: 视频时长
    :param ratio: 视频尺寸
    :returns: object
    """
    user_id = request.values['user_id']
    game_id = request.values['game_id']
    video = DaTangVideo.init()
    video.author = user_id
    video.game = game_id
    video.title = request.values['title']

    if not Guard.verify_sig(request.values.to_dict()):
        return error.AuthFailed

    # 敏感词检查
    if Spam.filter_words(video.title, 'video'):
        return error.InvalidContent
    try:
        duration = int(request.values['duration'])
    except:
        return error.InvalidArguments

    video.duration = duration
    video.ratio = request.values['ratio']
    # 设置为文件上传状态, 文件上传成功之后更改为上线状态
    video.status = const.UPLOADING
    vid = video.create_model()
    return DaTangVideo.get_one(vid, check_online=False).format()


@app.route('/datang/videos/<string:vid>/update-video', methods=('POST',))
@util.jsonapi(verify=False)
def datang_update_video(vid):
    """修改视频 (POST)

    :uri: /datang/videos/<string:vid>/update-video
    :param cover: 背景相对路径
    :param url: 视频相对路径
    :param upload_sig: 验证串
    :return: {'url': string}
    """
    cover = request.values.get('cover')
    url = request.values.get('url')
    valid_sig = request.values.get('upload_sig')
    md5 = hashlib.md5(vid)
    secret = '&%s' % ('29eb78ff3c8f20fe')
    md5.update(secret)
    if valid_sig != md5.hexdigest() or not cover or not url:
        return error.InvalidArguments

    video = DaTangVideo.get_one(vid, check_online=False)
    if not video:
        return error.VideoNotExist

    data = {'cover': cover, 'url': url, 'status': const.ONLINE}
    video = video.update_model({"$set": data})
    return {'video': video.format()}


@app.route('/datang/videos/<string:vid>/delete', methods=('POST',))
@util.jsonapi(verify=False)
def datang_delete_video(vid):
    """删除视频 (POST&LOGIN)

    :uri: /datang/videos/<string:vid>/delete
    :param user_id: 大唐用户ID
    :returns: {}
    """
    user_id = request.values.get('user_id')

    if not Guard.verify_sig(request.values.to_dict()):
        return error.AuthFailed

    video = DaTangVideo.get_one(vid, check_online=False)
    if not video:
        return error.VideoNotExist

    if user_id != str(video.author):
        return error.AuthFailed

    video.delete_model()
    return {}


@app.route('/datang/videos/<string:vid>/play', methods=['GET'])
def datang_play_video(vid):
    """播放视频 (GET)

    :uri: /datang/videos/<string:vid>/play
    :returns: redirect(real_url)
    """
    start = int(time.time() * 1000)
    video = DaTangVideo.get_one(vid)
    if not video:
        result = {
            'status': error.VideoNotExist.errno,
            'errmsg': error.VideoNotExist.errmsg,
            'data': {},
            'time': int(time.time() * 1000) - start,
        }
        return jsonify(result)

    video.update_model({'$inc': {'vv': 1}})
    return redirect(video.real_url())


@app.route('/datang/games/<string:gid>/popular/videos', methods=['GET'])
@util.jsonapi(verify=False)
def datang_game_popular_videos(gid):
    """获取游戏人气视频 (GET)

    :uri: /datang/games/<string:gid>/videos
    :param page: 页码
    :param nbr: 每页数量
    :returns: {'videos': list, 'end_page': bool}
    """
    params = request.values
    page = int(params.get('page', 1))
    pagesize = int(params.get('nbr', 10))

    videos = list()
    vids = DaTangVideo.game_hotvideo_ids(gid, page, pagesize)
    videos.extend([v.format() for v in DaTangVideo.get_list(vids)])
    return {'videos': videos, 'end_page': len(vids) != pagesize}


@app.route('/datang/users/<string:uid>/videos', methods=['GET'])
@util.jsonapi(verify=False)
def datang_user_videos(uid):
    """获取用户创建的视频 (GET)

    :uri: /datang/users/<string:uid>/videos
    :params game_id: 游戏id
    :param maxs: 最后时间, 0代表当前时间, 无此参数按page来分页
    :param page: 页码(数据可能有重复, 建议按照maxs分页)
    :param nbr: 每页数量
    :returns: {'videos': list, 'end_page': bool, 'maxs': timestamp}
    """
    params = request.values
    maxs = params.get('maxs', None)
    maxs = time.time() if maxs is not None and int(float(maxs)) == 0 else maxs and float(maxs)
    page = int(params.get('page', 1))
    pagesize = int(params.get('nbr', 10))
    gid = params.get('game_id', None)

    videos = list()
    vids = list()
    while len(videos) < pagesize:
        vids = DaTangVideo.user_game_video_ids(uid, gid, page, pagesize, maxs)
        videos.extend([v.format() for v in DaTangVideo.get_list(vids)])

        # 如果按照maxs分页, 不足pagesize个记录则继续查询
        if maxs is not None:
            obj = DaTangVideo.get_one(vids[-1], check_online=False) if vids else None
            maxs = obj.create_at if obj else 1000
            if len(vids) < pagesize:
                break
        else:
            break

    return {'videos': videos, 'end_page': len(vids) != pagesize, 'maxs': maxs}


@app.route("/datang/upload/upload-small-file", methods=("POST",))
@util.jsonapi(verify=False)
def datang_upload_small_file():
    """文件上传(POST&LOGIN)

    :uri: /datang/upload/upload-small-file
    :param type: 类型(videos.cover, videos.url)
    :param target_id: 对象id
    :param file: 上传文件
    :returns: {'target_id': string, 'type': string, 'url': string}
    """
    _type = request.form.get("type", None)
    target_id = request.form.get("target_id", None)
    if _type not in {"videos.cover", "videos.url"}:
        return error.InvalidArguments

    if not Guard.verify_sig(request.form.to_dict()):
        return error.AuthFailed

    video = DaTangVideo.get_one(str(target_id), check_online=False)
    if not video:
        return error.VideoNotExist

    # 上传文件
    _path = 'videos'
    _file = Media(app.config.get("STATIC_BASE"), _path, request.files['file'])
    try:
        url = _file.upload_file()
    except:
        return error.UploadFailed
    # 更新对象
    obj, attr = _type.split(".")
    data = {attr: url}
    if attr == 'url':
        data['status'] = const.ONLINE

    video.update_model({"$set": data})
    abs_url = urljoin(app.config.get('STATIC_URL'), url)
    return {'target_id': target_id, 'type': _type, 'url': abs_url}


def _set_upload_file_meta(file_id, meta):
    data = json.dumps(meta)
    key = "upload:%s" % file_id
    ok = Redis.setex(key, 3600 * 24, data)
    if not ok:
        raise


def _get_upload_file_meta(file_id):
    key = "upload:%s" % file_id
    data = Redis.get(key)
    return json.loads(data) if data else None


@app.route("/datang/upload/upload-large-file", methods=('POST',))
@util.jsonapi(verify=False)
def datang_upload_large_file():
    """大文件上传(POST&LOGIN)

    :uri: /datang/upload/upload-large-file
    :param type: 类型(videos.cover, videos.url)
    :param target_id: 对象id
    :param size: 文件大小
    :param ext: 文件后缀
    :returns: {'file_id': string, 'url': string}
    """
    _type = request.form.get("type", None)
    target_id = request.form.get("target_id", None)
    size = request.form.get("size", type=int)
    ext = request.form.get("ext")
    if _type not in {"videos.cover", "videos.url"}:
        return error.InvalidArguments

    if not Guard.verify_sig(request.form.to_dict()):
        return error.AuthFailed

    if not size or size <= 0:
        return error.InvalidArguments

    video = DaTangVideo.get_one(str(target_id), check_online=False)
    if not video:
        return error.VideoNotExist

    file_id = os.urandom(12).encode("hex")
    # 上传文件
    tmp_dir = os.path.join(app.config.get("STATIC_BASE"), "temp")
    file_path = os.path.join(tmp_dir, "l-%s.%s" % (file_id, ext))
    meta = dict(request.form.to_dict())
    meta['size'] = int(meta['size'])
    meta["file_id"] = file_id
    meta['path'] = file_path
    meta['user_id'] = video.author
    meta['ranges'] = list()
    try:
        _set_upload_file_meta(file_id, meta)
    except:
        return error.RedisFailed

    with open(file_path, "wb") as f:
        f.truncate(size)  # Pre-alloc file to get better performance on some fs.
    return {"file_id": file_id, "url": url_for("datang_upload_put_file", file_id=file_id)}


def _range_merge(result, r):
    # A range is a tuple that content (start, length).
    r0 = result[-1]
    if r0[0] + r0[1] >= r[0] + r[1]:
        # [0, 5[, [1, 3]
        # Do nothing, ignore r
        pass
    elif r0[0] + r0[1] >= r[0]:
        # [0, 5], [4, 6]
        l = r[0] - r0[0] + r[1]
        result[-1] = (r0[0], l,)
    else:
        # [0, 5], [6, 4]
        result.append(r)
    return result


@app.route("/datang/upload/<file_id>", methods=("GET",))
@util.jsonapi(verify=False)
def datang_upload_get_file_info(file_id):
    """获取大文件上传断点信息(GET&LOGIN)

    :uri: /datang/upload/<file_id>
    :returns: meta
    """
    meta = _get_upload_file_meta(file_id)
    if not meta:
        return error.UploadFailed('文件缓存信息不存在')
    meta.pop("path")
    return meta


@app.route("/datang/upload/<file_id>", methods=("PUT",))
@util.jsonapi(verify=False)
def datang_upload_put_file(file_id):
    """大文件断点上传(PUT&LOGIN)

    :uri: /datang/upload/<file_id>
    :header Range: 片段信息(bytes=offset-length)
    :header Content-Type: application/octet-stream
    :returns: {'size': int, 'total': tuple, 'ranges': list, 'complete': bool, 'url': url}
    """
    meta = _get_upload_file_meta(file_id)
    if not os.path.exists(meta['path']):
        return error.UploadFailed('临时文件不存在')

    new_range = None
    start_bytes = 0
    # 'Range: bytes=offset-length'
    if 'Range' in request.headers:
        range_str = request.headers['Range']
        start_bytes = int(range_str.split('=')[1].split('-')[0])
        if start_bytes < 0 or start_bytes >= meta['size']:
            return error.UploadFailed('上传Range数据有问题')

    with open(meta['path'], 'r+') as f:
        f.seek(start_bytes)
        f.write(request.data)
        new_range = [start_bytes, len(request.data)]

    url = None
    # 处理多线程问题, 进行上锁
    key = 'lock:upload:%s' % (file_id)
    while Redis.get(key):
        time.sleep(0.1)

    with util.Lockit(Redis, key) as locked:
        if locked:
            return error.RedisFailed
        meta = _get_upload_file_meta(file_id)
        file_range = meta['ranges']
        file_range.append(new_range)
        file_range.sort()
        meta['ranges'] = reduce(_range_merge, file_range, [[0, 0]])
        try:
            _set_upload_file_meta(file_id, meta)
        except:
            return error.RedisFailed

    total = reduce(lambda x, y: (0, x[1] + y[1]), meta['ranges'], [0, 0])
    complete = False
    if len(meta['ranges']) == 1 and meta['ranges'][0][1] == meta['size']:
        _path = 'videos' if meta['type'] == 'videos.url' else 'images'
        _file = Media(app.config.get("STATIC_BASE"), _path, None)
        try:
            url = _file.upload_large_file(meta['path'], None, '.%s' % meta['ext'])
        except:
            return error.UploadFailed
        # 更新对象
        obj, attr = meta['type'].split(".")
        data = {attr: url}
        if attr == 'url':
            data['status'] = const.ONLINE
        model = DaTangVideo.get_one(meta['target_id'], check_online=False)

        model.update_model({"$set": data})
        complete = True

    abs_url = urljoin(app.config.get('STATIC_URL'), url) if url else None
    return {'size': len(request.data), 'total': total, 'url': abs_url,
            'ranges': meta['ranges'], 'complete': complete}
