# -*- coding: utf8 -*-
from wanx import app

import esm
import os


class Spam(object):
    INDEX_MAP = dict()

    @classmethod
    def create_index(cls, ktype='default'):
        if ktype in cls.INDEX_MAP:
            return cls.INDEX_MAP[ktype]

        index = esm.Index()

        kw_path = app.config.get('BASE_DIR') or os.path.abspath(os.path.join(app.root_path, '../'))
        fname = os.path.join(kw_path, 'files/%s_keywords.txt' % (ktype))
        if not os.path.isfile(fname):
            fname = os.path.join(kw_path, 'files/default_keywords.txt')
            if not os.path.isfile(fname):
                return False

        with open(fname, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    index.enter(line)

        index.fix()
        cls.INDEX_MAP['ktype'] = index
        return index

    @classmethod
    def filter_words(cls, content, ktype='default'):
        if not content:
            return False
        index = cls.create_index(ktype)
        content = content.encode('utf8')
        return index.query(content) != []

    @classmethod
    def replace_words(cls, content, ktype='default', replace_str='*'):
        if not content:
            return content
        index = cls.create_index(ktype)
        content = content.encode('utf8')
        ret = index.query(content)
        for r in ret:
            content = content.replace(r[1], replace_str * len(r[1].decode('utf8')))
        return content
