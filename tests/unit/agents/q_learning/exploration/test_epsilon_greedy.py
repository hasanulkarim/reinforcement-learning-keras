import unittest

import numpy as np

from rlk.agents.q_learning.exploration.epsilon_greedy import EpsilonGreedy


class TestEpsilonGreedy(unittest.TestCase):
    _sut = EpsilonGreedy
    _mock_attribute = 4
    _actions_pool = list(range(3))

    def setUp(self) -> None:
        self._greedy_action = lambda: self._mock_attribute + 1

    def test_eps_1_returns_random_action_during_training(self):
        # Arrange
        eps = self._sut(eps_initial=1, actions_pool=self._actions_pool)

        # Act
        selection = eps.select(state=None, greedy_option=self._greedy_action, training=True)

        # Assert
        self.assertIn(selection, self._actions_pool)

    def test_eps_1_returns_greedy_action_if_not_training(self):
        # Arrange
        eps = self._sut(eps_initial=1, actions_pool=self._actions_pool)

        # Act
        selection = eps.select(state=None, greedy_option=self._greedy_action)

        # Assert
        self.assertEqual(5, selection)

    def test_eps_0_returns_greedy_action(self):
        # Arrange
        eps = self._sut(eps_initial=0, actions_pool=self._actions_pool)

        # Act
        selection = eps.select(state=None, greedy_option=self._greedy_action)

        # Assert
        self.assertEqual(5, selection)

    def test_training_selection_decays_eps(self):
        # Arrange
        initial_eps = 0.99
        eps = self._sut(eps_initial=initial_eps, actions_pool=self._actions_pool)

        # Act
        _ = eps.select(state=None, greedy_option=self._greedy_action, training=True)

        # Assert
        self.assertLess(eps.eps_current, initial_eps)

    def test_non_training_selection_doesnt_decay_eps(self):
        # Arrange
        initial_eps = 0.99
        eps = self._sut(eps_initial=initial_eps, actions_pool=self._actions_pool)

        # Act
        _ = eps.select(state=None, greedy_option=self._greedy_action, training=False)

        # Assert
        self.assertAlmostEqual(eps.eps_current, initial_eps)

    def test_training_call_with_0_decay_doesnt_decay_eps(self):
        # Arrange
        initial_eps = 0.99
        eps = self._sut(eps_initial=initial_eps, decay=0, actions_pool=self._actions_pool)

        # Act
        _ = eps.select(state=None, greedy_option=self._greedy_action, training=True)

        # Assert
        self.assertAlmostEqual(eps.eps_current, initial_eps)

    def test_epsilon_never_increases_when_perturb_is_off(self):
        # Arrange
        eps = self._sut(eps_initial=1, decay=0.00075, decay_schedule='compound', actions_pool=self._actions_pool)

        # Act
        future = eps.simulate(plot=False)

        # Assert
        self.assertTrue(np.all(np.diff(future) <= 0))

    def test_epsilon_never_increases_when_perturb_increase_every_is_0(self):
        # Arrange
        eps = self._sut(eps_initial=1, decay=0.00075, decay_schedule='compound',
                        perturb_increase_every=0, perturb_increase_mag=10, actions_pool=self._actions_pool)

        # Act
        future = eps.simulate(plot=False, steps=100000)

        # Assert
        self.assertTrue(np.all(np.diff(future) <= 0))

    def test_epsilon_never_increases_when_perturb_increase_mag_is_0(self):
        # Arrange
        eps = self._sut(eps_initial=1, decay=0.00075, decay_schedule='compound',
                        perturb_increase_every=10, perturb_increase_mag=0, actions_pool=self._actions_pool)

        # Act
        future = eps.simulate(plot=False, steps=100000)

        # Assert
        self.assertTrue(np.all(np.diff(future) <= 0))

    def test_perturb_increases_periodically_increases_epsilon_when_on(self):
        # Arrange
        eps = self._sut(eps_initial=1, decay=0.01, decay_schedule='compound', perturb_increase_every=1000,
                        perturb_increase_mag=0.5, actions_pool=self._actions_pool)

        # Act
        future = eps.simulate(plot=False, steps=100000)

        # Assert
        self.assertFalse(np.all(np.diff(future) <= 0))
