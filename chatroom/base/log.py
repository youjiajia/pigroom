# -*- coding: utf8 -*-
from wanx import app

import logging
import logging.handlers
import os


# 日志记录
log_root = os.path.abspath(os.path.join(app.root_path, '../logs'))
if not os.path.exists(log_root):
    os.makedirs(log_root)

appHandler = logging.handlers.TimedRotatingFileHandler(os.path.join(log_root, 'app.log'),
                                                       when="midnight")
logFormatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s '
                                 '[in %(pathname)s:%(lineno)d]')
appHandler.setFormatter(logFormatter)


my_loggers = dict()


def print_log(filename, message):
    my_logger = my_loggers.get(filename)
    if not my_logger:
        myhandler = logging.handlers.TimedRotatingFileHandler(
            os.path.join(log_root, '%s.log' % filename),
            when="midnight"
        )
        log_format = logging.Formatter('%(asctime)s: %(message)s')
        myhandler.setFormatter(log_format)
        my_logger = logging.getLogger(filename)
        my_logger.addHandler(myhandler)
        my_logger.setLevel(logging.INFO)
        my_loggers[filename] = my_logger
    my_logger.info(message)

__all__ = ['appHandler', 'print_log']
