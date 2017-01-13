# -*- coding: utf8 -*-
import os
import unittest

os.environ['WXENV'] = 'UnitTest'

if __name__ == "__main__":
    from wanx.tests.test_api import ApiTestCase
    from wanx.tests.test_fun import FunTestCase
    suite = unittest.TestSuite()
    # Test base cache functions
    suite.addTest(FunTestCase("test_cached_object"))
    suite.addTest(FunTestCase("test_cached_hash"))
    suite.addTest(FunTestCase("test_cached_set"))
    suite.addTest(FunTestCase("test_cached_list"))
    suite.addTest(FunTestCase("test_cached_zset"))
    suite.addTest(FunTestCase("test_spam"))
    suite.addTest(FunTestCase("test_pinyin"))
    suite.addTest(FunTestCase("test_config"))

    suite.addTest(ApiTestCase("test_task"))

    # First test without cache
    suite.addTest(ApiTestCase("test_comment"))
    suite.addTest(ApiTestCase("test_share"))
    suite.addTest(ApiTestCase("test_migu"))
    suite.addTest(ApiTestCase("test_upload_large"))
    suite.addTest(ApiTestCase("test_msg"))
    suite.addTest(ApiTestCase("test_activity"))
    # 因为对方有ip限制而无法进行测试
    # suite.addTest(ApiTestCase("test_traffic"))

    # Second test with cache
    suite.addTest(ApiTestCase("test_game"))
    suite.addTest(ApiTestCase("test_web_game"))
    suite.addTest(ApiTestCase("test_video"))
    suite.addTest(ApiTestCase("test_comment"))
    suite.addTest(ApiTestCase("test_user"))
    suite.addTest(ApiTestCase("test_share"))
    suite.addTest(ApiTestCase("test_migu"))
    suite.addTest(ApiTestCase("test_live"))
    suite.addTest(ApiTestCase("test_task_finished"))
    suite.addTest(ApiTestCase("test_gift"))
    suite.addTest(ApiTestCase("test_activity"))
    suite.addTest(ApiTestCase("test_store"))

    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
