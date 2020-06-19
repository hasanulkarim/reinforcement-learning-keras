import os
from dataclasses import dataclass
from typing import Dict, Any, Union, Tuple, Iterable, Callable

import joblib
import numpy as np
import tensorflow as tf
from tensorflow import keras

from agents.agent_base import AgentBase
from agents.components.helpers.env_builder import EnvBuilder
from agents.components.helpers.virtual_gpu import VirtualGPU
from agents.components.history.training_history import TrainingHistory
from agents.components.replay_buffers.continuous_buffer import ContinuousBuffer
from agents.q_learning.exploration.epsilon_greedy import EpsilonGreedy
from enviroments.config_base import ConfigBase
from enviroments.model_base import ModelBase

tf.compat.v1.disable_eager_execution()


@dataclass
class DeepQAgent(AgentBase):
    replay_buffer: ContinuousBuffer
    eps: EpsilonGreedy
    training_history: TrainingHistory
    model_architecture: ModelBase
    env_spec: str = "CartPole-v0"
    env_wrappers: Iterable[Callable] = ()
    name: str = 'DQNAgent'
    gamma: float = 0.99
    replay_buffer_samples: int = 75
    final_reward: Union[float, None] = None

    def __post_init__(self) -> None:
        self.env_builder = EnvBuilder(self.env_spec, self.env_wrappers)
        self._build_model()
        self._fn = f"{self.name}_{self.env_spec}"
        self.ready = True

    def __getstate__(self) -> Dict[str, Any]:
        return self._pickle_compatible_getstate()

    def _save_models_and_buffer(self):
        if not os.path.exists(f"{self._fn}"):
            os.mkdir(f"{self._fn}")

        self._action_model.save(f"{self._fn}/action_model")
        self._value_model.save(f"{self._fn}/value_model")
        self.replay_buffer.save(f"{self._fn}/replay_buffer.joblib")

    def _load_models_and_buffer(self):
        self._action_model = keras.models.load_model(f"{self._fn}/action_model")
        self._value_model = keras.models.load_model(f"{self._fn}/value_model")
        self.replay_buffer = ContinuousBuffer.load(f"{self._fn}/replay_buffer.joblib")

    def unready(self) -> None:
        if self.ready:
            self._save_models_and_buffer()
            self._action_model = None
            self._value_model = None
            self.replay_buffer = None
            keras.backend.clear_session()
            tf.compat.v1.reset_default_graph()
        super().unready()

    def check_ready(self):

        if not self.ready:
            self._load_models_and_buffer()

            super().check_ready()

    def _build_model(self) -> None:
        """
        Prepare two of the same model.

        The action model is used to pick actions and the value model is used to predict value of Q(s', a). Action model
        weights are updated on every buffer sample + training step. The value model is never directly trained, but it's
        weights are updated to match the action model at the end of each episode.

        :return:
        """
        self.model_architecture.compile(model_name='action_model')

        self._action_model = self.model_architecture.compile(model_name='action_model', loss='mse')
        self._value_model = self.model_architecture.compile(model_name='value_model', loss='mse')

    def transform(self, s: np.ndarray) -> np.ndarray:
        """Check input shape, add Row dimension if required."""

        if len(s.shape) < len(self._action_model.input.shape):
            s = np.expand_dims(s, 0)

        return s

    def update_experience(self, s: np.ndarray, a: int, r: float, d: bool) -> None:
        """
        First the most recent step is added to the buffer.

        Note that s' isn't saved because there's no need. It'll be added next step. s' for any s is always index + 1 in
        the buffer.
        """

        # Add s, a, r, d to experience buffer
        self.replay_buffer.append((s, a, r, d))

    def update_model(self) -> None:
        """
        Sample a batch from the replay buffer, calculate targets using value model, and train action model.

        If the buffer is below its minimum size, no training is done.

        If the buffer has reached its minimum size, a training batch from the replay buffer and the action model is
        updated.

        This update samples random (s, a, r, s') sets from the buffer and calculates the discounted reward for each set.
        The value of the actions at states s and s' are predicted from the value model. The action model is updated
        using these value predictions as the targets. The value of performed action is updated with the discounted
        reward (using its value prediction at s'). ie. x=s, y=[action value 1, action value 2].

        GPU Performance notes (with 1080ti and eps @ 0.01, while rendering pong):
          - Looping here with 2 predict calls and 1 train call (each single rows) is unusably slow.
          - Two predict calls before loop and 1 train call after (on batches) runs at ~16 fps for pong (~2 GPU util).
          - Switching TF to non-eager mode improves performance to 50fps (~7% GPU util) (also stops memory leaks).
          - Reducing the predict calls to 1 by joining s and s' increases performance to ~73 fps (~14% util).
            - Render off: ~81fps (~16% util)
          - Vectorizing out the remaining loop: ~73fps (~14% util)
            - Render off: ~84fps (~16% util)
        """

        # If buffer isn't full, don't train
        if not self.replay_buffer.full:
            return

        # Else sample batch from buffer
        ss, aa, rr, dd, ss_ = self.replay_buffer.sample_batch(self.replay_buffer_samples)

        # Calculate estimated S,A values for current states and next states. These are stacked together first to avoid
        # making two separate predict calls
        ss = np.array(ss)
        ss_and_ss_ = np.vstack((ss, np.array(ss_)))
        y_now_and_future = self._value_model.predict_on_batch(ss_and_ss_)
        y_now = y_now_and_future[0:self.replay_buffer_samples]
        y_future = y_now_and_future[self.replay_buffer_samples::]

        # Update rewards where not done with y_future predictions
        dd_mask = np.array(dd, dtype=bool)
        rr = np.array(rr, dtype=float)
        rr[~dd_mask] += np.max(y_future[~dd_mask, :], axis=1)
        # If self.final_reward is set, set done cases to this value. Else leave as observed reward.
        if self.final_reward is not None:
            rr[dd_mask] = self.final_reward

        # Gather max action indexes and update relevent actions in y
        aa = np.array(aa, dtype=int)
        np.put_along_axis(y_now, aa.reshape(-1, 1), rr.reshape(-1, 1), axis=1)

        # Fit model with updated y_now values
        self._action_model.train_on_batch(ss, y_now)

    def get_best_action(self, s: np.ndarray) -> np.ndarray:
        """
        Get best action(s) from model - the one with the highest predicted value.
        :param s: A single or multiple rows of state observations.
        :return: The selected action.
        """

        preds = self._action_model.predict(self.transform(s))

        return np.argmax(preds)

    def get_action(self, s: np.ndarray, training: bool = False) -> int:
        """
        Get an action using epsilon greedy.

        Epsilon decays every time a random action is chosen.

        :param s: The raw state observation.
        :param training: Bool to indicate whether or not to use this experience to update the model. If False, just
                         returns best action.
        :return: The selected action.
        """
        action = self.eps.select(greedy_option=lambda: self.get_best_action(s),
                                 random_option=lambda: self.env.action_space.sample(),
                                 training=training)

        return action

    def update_value_model(self) -> None:
        """
        Update the value model with the weights of the action model (which is updated each step).

        The value model is updated less often to aid stability.
        """
        self._value_model.set_weights(self._action_model.get_weights())

    def _play_episode(self, max_episode_steps: int = 500,
                      training: bool = False, render: bool = True) -> Tuple[float, int]:
        """
        Play a single episode and return the total reward.

        :param max_episode_steps: Max steps before stopping, overrides any time limit set by Gym.
        :param training: Bool to indicate whether or not to use this experience to update the model.
        :param render: Bool to indicate whether or not to call env.render() each training step.
        :return: The total real reward for the episode.
        """
        self.env._max_episode_steps = max_episode_steps
        obs = self.env.reset()
        total_reward = 0
        for frame in range(max_episode_steps):
            action = self.get_action(obs, training=training)
            prev_obs = obs
            obs, reward, done, info = self.env.step(action)
            total_reward += reward

            if render:
                self.env.render()

            if training:
                self.update_experience(s=prev_obs, a=action, r=reward, d=done)
                # Action model is updated in TD(λ) fashion
                self.update_model()

            if done:
                break

        return total_reward, frame

    def _after_episode_update(self) -> None:
        """Value model synced with action model at the end of each episode."""
        self.update_value_model()

    @classmethod
    def example(cls, config: ConfigBase, render: bool = True,
                n_episodes: int = 500, max_episode_steps: int = 500, update_every: int = 10,
                checkpoint_every: int = 100) -> "DeepQAgent":
        """Create, train, and save agent for a given config."""
        VirtualGPU(config.gpu_memory)
        config_dict = config.build()

        agent = cls(**config_dict)

        agent.train(verbose=True, render=render,
                    n_episodes=n_episodes, max_episode_steps=max_episode_steps, update_every=update_every,
                    checkpoint_every=checkpoint_every)
        agent.save()

        return agent

    def save(self) -> None:
        if not os.path.exists(f"{self._fn}"):
            os.mkdir(f"{self._fn}")

        joblib.dump(self, f"{self._fn}/agent.joblib")
        self.check_ready()

    @classmethod
    def load(cls, fn: str) -> "DeepQAgent":
        new_agent = joblib.load(f"{fn}/agent.joblib")
        new_agent.check_ready()

        return new_agent


if __name__ == "__main__":
    from enviroments.pong.pong_config import PongConfig
    from enviroments.cart_pole.cart_pole_config import CartPoleConfig
    from enviroments.mountain_car.mountain_car_config import MountainCarConfig

    # DQNs
    agent_cart_pole = DeepQAgent.example(CartPoleConfig(agent_type='dqn', plot_during_training=True), render=False)
    agent_mountain_car = DeepQAgent.example(MountainCarConfig(agent_type='dqn', plot_during_training=True))
    agent_pong = DeepQAgent.example(PongConfig(agent_type='dqn', plot_during_training=True),
                                    max_episode_steps=10000, update_every=5, render=False, checkpoint_every=10)

    # Dueling DQNs
    dueling_agent_cart_pole = DeepQAgent.example(CartPoleConfig(agent_type='dueling_dqn', plot_during_training=True))
    dueling_agent_mountain_car = DeepQAgent.example(MountainCarConfig(agent_type='dueling_dqn',
                                                                      plot_during_training=True))