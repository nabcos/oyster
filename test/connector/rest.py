import tempfile
import unittest
from hamcrest import *

import connector.rest

import oyster
import os
import mock
import oysterconfig
import shutil

__author__ = 'hanzelm'

class RestTests(unittest.TestCase):

    test_dir = tempfile.mkdtemp()

    def create_dummy_config_file(self):
        """
        FIXME: we're only able to mock config if this file exists
        """
        if not os.path.exists("config"):
            os.mkdir("config")

        config_file = file("config/default", 'w')
        config_file.write("DUMMY")
        config_file.close()

    def setUp(self):
        super(RestTests, self).setUp()

        self.create_dummy_config_file()

        test_config = {"savedir": self.test_dir, "basedir": self.test_dir, "vol_get_cmd": "echo 1", "vol_filter_regexp": "(.)"}

        oysterconfig.getConfig = mock.MagicMock(name="getConfig", return_value=test_config )
        oyster.PlaylistBuilder = mock.MagicMock(name="PlaylistBuilder")

        self.oyster = oyster.Oyster()

        self.under_test = connector.rest.RestController(self.oyster)

    def tearDown(self):
        shutil.rmtree(self.test_dir)
        shutil.rmtree("config")
        super( RestTests, self ).tearDown( )

    def testSkip(self):
        assert_that(self.oyster.nextreason, equal_to(''))
        self.under_test.next()
        assert_that(self.oyster.nextreason, equal_to('SKIPPED'))
