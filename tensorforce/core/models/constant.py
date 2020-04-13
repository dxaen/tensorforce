# Copyright 2018 Tensorforce Team. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

import numpy as np
import tensorflow as tf

from tensorforce import TensorforceError
from tensorforce.core import TensorDict, tf_function, tf_util
from tensorforce.core.models import Model


class ConstantModel(Model):
    """
    Utility class to return constant actions of a desired shape and with given bounds.
    """

    def __init__(
        self,
        # Model
        states, actions, name, device, parallel_interactions, summarizer, config,
        # ConstantModel
        action_values
    ):
        super().__init__(
            # Model
            states=states, actions=actions, preprocessing=None, exploration=0.0, variable_noise=0.0,
            l2_regularization=0.0, name=name, device=None,
            parallel_interactions=parallel_interactions, saver=None, summarizer=summarizer,
            config=config
        )

        self.action_values = dict()
        if action_values is not None:
            for name, spec in self.actions_spec.items():
                if name not in action_values:
                    continue
                value = spec.py_type()(action_values[name])
                if spec.type != 'bool' and spec.min_value is not None and value < spec.min_value:
                    raise TensorforceError.value(
                        name='ConstantAgent', argument='action_values[{}]'.format(name),
                        value=value, hint='> max_value'
                    )
                if spec.type != 'bool' and spec.max_value is not None and value > spec.max_value:
                    raise TensorforceError.value(
                        name='ConstantAgent', argument='action_values[{}]'.format(name),
                        value=value, hint='> max_value'
                    )
                self.action_values[name] = value

    @tf_function(num_args=3)
    def core_act(self, states, internals, auxiliaries, deterministic):
        assert len(internals) == 0

        actions = TensorDict()
        for name, spec in self.actions_spec.items():
            shape = tf.concat(values=(
                tf_util.cast(x=tf.shape(input=states.item())[:1], dtype='int'),
                tf_util.constant(value=spec.shape, dtype='int')
            ), axis=0)

            if self.action_values is not None and name in self.action_values:
                # If user-specified, choose given action
                action = tf_util.constant(value=self.action_values[name], dtype=spec.type)
                actions[name] = tf.fill(dims=shape, value=action)

            elif self.config.enable_int_action_masking and spec.type == 'int' and \
                    spec.num_values is not None:
                # If masking, choose first unmasked action
                mask = auxiliaries[name + '_mask']
                choices = tf_util.constant(
                    value=list(range(spec.num_values)), dtype='int',
                    shape=(tuple(1 for _ in spec.shape) + (1, spec.num_values))
                )
                one = tf_util.constant(value=1, dtype='int', shape=(1,))
                multiples = tf.concat(values=(shape, one), axis=0)
                choices = tf.tile(input=choices, multiples=multiples)
                choices = tf.boolean_mask(tensor=choices, mask=mask)
                mask = tf_util.cast(x=mask, dtype='int')
                num_unmasked = tf.math.reduce_sum(input_tensor=mask, axis=(spec.rank + 1))
                masked_offset = tf.math.cumsum(x=num_unmasked, axis=spec.rank, exclusive=True)
                actions[name] = tf.gather(params=choices, indices=masked_offset)

            elif spec.type != 'bool' and spec.min_value is not None:
                if spec.max_value is not None:
                    # If min/max_value given, choose mean action
                    action = spec.min_value + 0.5 * (spec.max_value - spec.min_value)
                    action = tf_util.constant(value=action, dtype=spec.type)
                    actions[name] = tf.fill(dims=shape, value=action)

                else:
                    # If only min_value given, choose min_value
                    action = tf_util.constant(value=spec.min_value, dtype=spec.type)
                    actions[name] = tf.fill(dims=shape, value=action)

            elif spec.type != 'bool' and spec.max_value is not None:
                # If only max_value given, choose max_value
                action = tf_util.constant(value=spec.max_value, dtype=spec.type)
                actions[name] = tf.fill(dims=shape, value=action)

            else:
                # Else choose zero
                actions[name] = tf_util.zeros(shape=shape, dtype=spec.type)

        return actions, TensorDict()

    @tf_function(num_args=6)
    def core_observe(self, states, internals, auxiliaries, actions, terminal, reward):
        return tf_util.constant(value=False, dtype='bool')
