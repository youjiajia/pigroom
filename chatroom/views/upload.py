# -*- coding: utf8 -*-
from flask import request, url_for
from bson.objectid import ObjectId
from wanx import app
from wanx.base.xredis import Redis
from wanx.base import util, error, const
from wanx.base.media import Media
from wanx.models.video import Video
from wanx.models.user import User
from wanx.models.task import UserTask, SET_HEADER
from urlparse import urljoin

import json
import os
import time


@app.route("/upload/upload-small-file", methods=("POST",))
@util.jsonapi(login_required=True, verify=False)
def upload_small_file():
    """文件上传(POST&LOGIN)

    :uri: /upload/upload-small-file
    :param type: 类型(videos.cover, videos.url, users.logo, users.photo)
    :param target_id: 对象id
    :param file: 上传文件
    :returns: {'target_id': string, 'type': string, 'url': string}
    """
    _type = request.form.get("type", None)
    target_id = request.form.get("target_id", None)
    if _type not in {"videos.cover", "videos.url", "users.logo", "users.photo"}:
        return error.InvalidArguments

    try:
        ObjectId(target_id)
    except:
        return error.InvalidArguments

    user = request.authed_user
    if _type.startswith("users.") and str(user._id) != target_id:
        return error.AuthFailed

    if _type.startswith("videos."):
        video = Video.get_one(str(target_id), check_online=False)
        if str(user._id) != str(video.author):
            return error.AuthFailed
    # 上传文件
    _path = 'videos' if _type == 'videos.url' else 'images'
    _file = Media(app.config.get("STATIC_BASE"), _path, request.files['file'])
    try:
        url = _file.upload_file()
    except:
        return error.UploadFailed
    # 更新对象
    obj, attr = _type.split(".")
    data = {attr: url}
    if obj == 'videos':
        if attr == 'url':
            data['status'] = const.ONLINE
        model = Video.get_one(target_id, check_online=False)
    elif obj == 'users':
        model = User.get_one(target_id, check_online=False)

    model.update_model({"$set": data})

    # 设置头像任务检查
    if obj == 'users' and user:
        UserTask.check_user_tasks(str(user._id), SET_HEADER, 1)

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


@app.route("/upload/upload-large-file", methods=('POST',))
@util.jsonapi(login_required=True, verify=False)
def upload_large_file():
    """大文件上传(POST&LOGIN)

    :uri: /upload/upload-large-file
    :param type: 类型(videos.cover, videos.url, users.log, users.photo)
    :param target_id: 对象id
    :param size: 文件大小
    :param ext: 文件后缀
    :returns: {'file_id': string, 'url': string}
    """
    _type = request.form.get("type", None)
    target_id = request.form.get("target_id", None)
    size = request.form.get("size", type=int)
    ext = request.form.get("ext")
    if _type not in {"videos.cover", "videos.url", "users.logo", "users.photo"}:
        return error.InvalidArguments

    if not size or size <= 0:
        return error.InvalidArguments

    try:
        ObjectId(target_id)
    except:
        return error.InvalidArguments

    user = request.authed_user
    if _type.startswith("users.") and str(user._id) != target_id:
        return error.AuthFailed

    if _type.startswith("videos."):
        video = Video.get_one(str(target_id), check_online=False)
        if str(user._id) != str(video.author):
            return error.AuthFailed

    file_id = os.urandom(12).encode("hex")
    # 上传文件
    tmp_dir = os.path.join(app.config.get("STATIC_BASE"), "temp")
    file_path = os.path.join(tmp_dir, "l-%s.%s" % (file_id, ext))
    meta = dict(request.form.to_dict())
    meta['size'] = int(meta['size'])
    meta["file_id"] = file_id
    meta['path'] = file_path
    meta['user_id'] = str(user._id)
    meta['ranges'] = list()
    try:
        _set_upload_file_meta(file_id, meta)
    except:
        return error.RedisFailed

    with open(file_path, "wb") as f:
        f.truncate(size)  # Pre-alloc file to get better performance on some fs.
    return {"file_id": file_id, "url": url_for("upload_put_file", file_id=file_id)}


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


@app.route("/upload/<file_id>", methods=("GET",))
@util.jsonapi(login_required=True, verify=False)
def upload_get_file_info(file_id):
    """获取大文件上传断点信息(GET&LOGIN)

    :uri: /upload/<file_id>
    :returns: meta
    """
    meta = _get_upload_file_meta(file_id)
    if not meta:
        return error.UploadFailed('文件缓存信息不存在')
    meta.pop("path")
    return meta


@app.route("/upload/<file_id>", methods=("PUT",))
@util.jsonapi(login_required=True, verify=False)
def upload_put_file(file_id):
    """大文件断点上传(PUT&LOGIN)

    :uri: /upload/<file_id>
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
        if obj == 'videos':
            if attr == 'url':
                data['status'] = const.ONLINE
            model = Video.get_one(meta['target_id'], check_online=False)
        elif obj == 'users':
            model = User.get_one(meta['target_id'], check_online=False)

        model.update_model({"$set": data})
        complete = True

    abs_url = urljoin(app.config.get('STATIC_URL'), url) if url else None
    return {'size': len(request.data), 'total': total, 'url': abs_url,
            'ranges': meta['ranges'], 'complete': complete}
