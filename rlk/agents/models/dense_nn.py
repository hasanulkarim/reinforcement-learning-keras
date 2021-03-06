from typing import Tuple

from tensorflow import keras

from rlk.agents.models.model_base import ModelBase


class DenseNN(ModelBase):

    def _model_architecture(self) -> Tuple[keras.layers.Layer, keras.layers.Layer]:
        frame_input = keras.layers.Input(name='input', shape=self.observation_shape)

        # This flatten handles time buffered observations; for example if obs is (115, t) rather than (115 * t).
        # Converts to (115 * t).
        flat = keras.layers.Flatten(name='flatten')(frame_input)

        fc1 = keras.layers.Dense(int(flat.shape[1] / 1.5), name='fc1', activation='relu')(flat)
        fc2 = keras.layers.Dense(int(flat.shape[1] / 3), name='fc2', activation='relu')(fc1)
        fc3 = keras.layers.Dense(self.n_actions * 2, name='fc3', activation='relu')(fc2)

        action_output = self._add_output(input_layer=fc3)

        return frame_input, action_output
