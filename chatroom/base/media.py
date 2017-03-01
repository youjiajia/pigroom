# -*- coding: utf8 -*-
from werkzeug import secure_filename

import hashlib
import os
import time

MAX_SMALL_FILE_SIZE = 1024 * 1024 * 1024
MAX_LARGE_FILE_SIZE = 1024 * 1024 * 1024
READ_BUFF_SIZE = 128 * 1024
UPLOAD_TRUNK_SIZE = 1024 * 1024

ALLOWED_EXT = {"jpg", "jpeg", "png", "gif", "mp4"}


class Media(object):

    @classmethod
    def get_file_md5(cls, file_path):
        md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            while True:
                data = f.read(READ_BUFF_SIZE)
                md5.update(data)
                if len(data) < READ_BUFF_SIZE:
                    break
        return md5.hexdigest()

    def __init__(self, root, sub_dir, upload_file):
        self.root = root
        self.sub_dir = sub_dir
        self.upload = upload_file

    def _get_tmp_path(self):
        tmp_dir = os.path.join(self.root, "temp")
        if not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir)
        tmp_path = os.path.join(tmp_dir, "s-%d-%s" %
                                (int(time.time() * 1000), os.urandom(4).encode("hex")))
        return tmp_path

    def _save_file(self, path):
        md5 = hashlib.md5()
        with open(path, "wb") as f:
            for _ in range(MAX_SMALL_FILE_SIZE, 0, -READ_BUFF_SIZE):
                data = self.upload.read(READ_BUFF_SIZE)
                md5.update(data)
                f.write(data)
                if len(data) < READ_BUFF_SIZE:
                    break
        return path, md5.hexdigest()

    def _get_ext(self):
        ext = os.path.splitext(self.upload.filename)[-1]
        return ext

    def _rename_temp_file(self, tmp_path, name=None, ext=None):
        name = name if name else self.get_file_md5(tmp_path)
        # 文件太小返回错误
        if os.stat(tmp_path).st_size < 200:
            os.remove(tmp_path)
            raise ValueError('file is too small')

        filename = secure_filename('%s%s' % (name, ext))
        folder = os.path.join(self.root, self.sub_dir, name[:3])
        if not os.path.exists(folder):
            os.makedirs(folder)

        new_path = os.path.join(folder, filename)
        if os.path.exists(new_path):
            os.remove(tmp_path)
        else:
            os.rename(tmp_path, new_path)
        url = os.path.join('/', self.sub_dir, name[:3], filename)
        return url

    def upload_file(self):
        ext = self._get_ext()

        _tmp_path = self._get_tmp_path()
        tmp_path, name = self._save_file(_tmp_path)

        url = self._rename_temp_file(tmp_path, name, ext)
        return url

    def upload_large_file(self, tmp_path, name, ext):
        url = self._rename_temp_file(tmp_path, name, ext)
        return url
