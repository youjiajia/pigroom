# -*- coding: utf8 -*-


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