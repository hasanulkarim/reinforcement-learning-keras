import unittest
from unittest.mock import MagicMock

import rlk.environments.doom as doom
from tests.unit.environments.atari.pong.test_pong_config import TestPongConfig

if doom.AVAILABLE:
    run_tests = True
else:
    run_tests = False
    doom = MagicMock()


@unittest.skipUnless(run_tests, reason='ViZDoomGym not installed')
class TestDoomConfig(TestPongConfig):
    def setUp(self):
        from rlk.environments.doom.doom_default_config import DoomDefaultConfig
        self._sut = DoomDefaultConfig
        self._agent_type = 'dueling_dqn'


del TestPongConfig
