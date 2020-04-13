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

from tensorforce import TensorforceError, util
from tensorforce.core import TensorSpec, tf_function, tf_util
from tensorforce.core.layers import TemporalLayer, TransformationBase


class InternalRnn(TemporalLayer, TransformationBase):
    """
    Internal state RNN cell layer (specification key: `internal_rnn`).

    Args:
        cell ('gru' | 'lstm'): The recurrent cell type
            (<span style="color:#C00000"><b>required</b></span>).
        size (int >= 0): Layer output size, 0 implies additionally removing the axis
            (<span style="color:#C00000"><b>required</b></span>).
        horizon (parameter, long >= 0): Past horizon
            (<span style="color:#C00000"><b>required</b></span>).
        bias (bool): Whether to add a trainable bias variable
            (<span style="color:#00C000"><b>default</b></span>: false).
        activation ('crelu' | 'elu' | 'leaky-relu' | 'none' | 'relu' | 'selu' | 'sigmoid' |
            'softmax' | 'softplus' | 'softsign' | 'swish' | 'tanh'): Activation nonlinearity
            (<span style="color:#00C000"><b>default</b></span>: none).
        dropout (parameter, 0.0 <= float < 1.0): Dropout rate
            (<span style="color:#00C000"><b>default</b></span>: 0.0).
        vars_trainable (bool): Whether layer variables are trainable
            (<span style="color:#00C000"><b>default</b></span>: true).
        summary_labels ('all' | iter[string]): Labels of summaries to record
            (<span style="color:#00C000"><b>default</b></span>: inherit value of parent module).
        l2_regularization (float >= 0.0): Scalar controlling L2 regularization
            (<span style="color:#00C000"><b>default</b></span>: inherit value of parent module).
        name (string): Layer name
            (<span style="color:#00C000"><b>default</b></span>: internally chosen).
        input_spec (specification): <span style="color:#00C000"><b>internal use</b></span>.
        kwargs: Additional arguments for Keras RNN cell layer, see
            `TensorFlow docs <https://www.tensorflow.org/api_docs/python/tf/keras/layers>`__.
    """

    def __init__(
        self, cell, size, horizon, bias=False, activation=None, dropout=0.0, vars_trainable=True,
        summary_labels=None, l2_regularization=None, name=None, input_spec=None, **kwargs
    ):
        super().__init__(
            temporal_processing='iterative', horizon=horizon, size=size, bias=bias,
            activation=activation, dropout=dropout, vars_trainable=vars_trainable,
            summary_labels=summary_labels, l2_regularization=l2_regularization,  name=name,
            input_spec=input_spec
        )

        self.cell_type = cell
        if self.cell_type == 'gru':
            self.cell = tf.keras.layers.GRUCell(
                units=self.size, name='cell', **kwargs  # , dtype=tf_util.get_dtype(type='float')
            )
        elif self.cell_type == 'lstm':
            self.cell = tf.keras.layers.LSTMCell(
                units=self.size, name='cell', **kwargs  # , dtype=tf_util.get_dtype(type='float')
            )
        else:
            raise TensorforceError.value(
                name='Rnn', argument='cell', value=self.cell_type, hint='not in {gru,lstm}'
            )

    def default_input_spec(self):
        return TensorSpec(type='float', shape=(0,))

    def output_spec(self):
        output_spec = super().output_spec()

        if self.squeeze:
            output_spec.shape = output_spec.shape[:-1]
        else:
            output_spec.shape = output_spec.shape[:-1] + (self.size,)

        output_spec.min_value = None
        output_spec.max_value = None

        return output_spec

    @property
    def internals_spec(self):
        internals_spec = super().internals_spec

        if self.cell_type == 'gru':
            shape = (self.size,)
        elif self.cell_type == 'lstm':
            shape = (2, self.size)

        internals_spec['state'] = TensorSpec(type='float', shape=shape)

        return internals_spec

    def internals_init(self):
        internals_init = super().internals_init()

        if self.cell_type == 'gru':
            shape = (self.size,)
        elif self.cell_type == 'lstm':
            shape = (2, self.size)

        stddev = min(0.1, np.sqrt(2.0 / self.size))
        internals_init['state'] = np.random.normal(scale=stddev, size=shape)

        return internals_init

    def initialize(self):
        super().initialize()

        if self.device is not None:
            self.device.__enter__()
        self.cell.build(input_shape=self.input_spec.shape[0])
        if self.device is not None:
            self.device.__exit__(None, None, None)

    @tf_function(num_args=0)
    def regularize(self):
        regularization_loss = super().regularize()

        if len(self.rnn.losses) > 0:
            regularization_loss += tf.math.add_n(inputs=self.cell.losses)

        return regularization_loss

    @tf_function(num_args=2)
    def iterative_step(self, x, internals):
        state = internals['state']

        if self.cell_type == 'gru':
            state = (state,)
        elif self.cell_type == 'lstm':
            state = (state[:, 0, :], state[:, 1, :])

        x = tf_util.float32(x=x)
        state = util.fmap(function=tf_util.float32, xs=state)

        x, state = self.cell(inputs=x, states=state)

        x = tf_util.cast(x=x, dtype='float')
        state = util.fmap(function=(lambda x: tf_util.cast(x=x, dtype='float')), xs=state)

        if self.cell_type == 'gru':
            internals['state'] = state[0]
        elif self.cell_type == 'lstm':
            internals['state'] = tf.stack(values=state, axis=1)

        return x, internals


class InternalGru(InternalRnn):
    """
    Internal state GRU cell layer (specification key: `internal_gru`).

    Args:
        cell ('gru' | 'lstm'): The recurrent cell type
            (<span style="color:#C00000"><b>required</b></span>).
        size (int >= 0): Layer output size, 0 implies additionally removing the axis
            (<span style="color:#C00000"><b>required</b></span>).
        horizon (parameter, long >= 0): Past horizon
            (<span style="color:#C00000"><b>required</b></span>).
        bias (bool): Whether to add a trainable bias variable
            (<span style="color:#00C000"><b>default</b></span>: false).
        activation ('crelu' | 'elu' | 'leaky-relu' | 'none' | 'relu' | 'selu' | 'sigmoid' |
            'softmax' | 'softplus' | 'softsign' | 'swish' | 'tanh'): Activation nonlinearity
            (<span style="color:#00C000"><b>default</b></span>: none).
        dropout (parameter, 0.0 <= float < 1.0): Dropout rate
            (<span style="color:#00C000"><b>default</b></span>: 0.0).
        vars_trainable (bool): Whether layer variables are trainable
            (<span style="color:#00C000"><b>default</b></span>: true).
        summary_labels ('all' | iter[string]): Labels of summaries to record
            (<span style="color:#00C000"><b>default</b></span>: inherit value of parent module).
        l2_regularization (float >= 0.0): Scalar controlling L2 regularization
            (<span style="color:#00C000"><b>default</b></span>: inherit value of parent module).
        name (string): Layer name
            (<span style="color:#00C000"><b>default</b></span>: internally chosen).
        input_spec (specification): <span style="color:#00C000"><b>internal use</b></span>.
        kwargs: Additional arguments for Keras GRU layer, see
            `TensorFlow docs <https://www.tensorflow.org/api_docs/python/tf/keras/layers/GRUCell>`__.
    """

    def __init__(
        self, size, horizon, bias=False, activation=None, dropout=0.0, vars_trainable=True,
        summary_labels=None, l2_regularization=None, name=None, input_spec=None, **kwargs
    ):
        super().__init__(
            cell='gru', size=size, horizon=horizon, bias=bias, activation=activation,
            dropout=dropout, vars_trainable=vars_trainable, summary_labels=summary_labels,
            l2_regularization=l2_regularization, name=name, input_spec=input_spec, **kwargs
        )


class InternalLstm(InternalRnn):
    """
    Internal state LSTM cell layer (specification key: `internal_lstm`).

    Args:
        cell ('gru' | 'lstm'): The recurrent cell type
            (<span style="color:#C00000"><b>required</b></span>).
        size (int >= 0): Layer output size, 0 implies additionally removing the axis
            (<span style="color:#C00000"><b>required</b></span>).
        horizon (parameter, long >= 0): Past horizon
            (<span style="color:#C00000"><b>required</b></span>).
        bias (bool): Whether to add a trainable bias variable
            (<span style="color:#00C000"><b>default</b></span>: false).
        activation ('crelu' | 'elu' | 'leaky-relu' | 'none' | 'relu' | 'selu' | 'sigmoid' |
            'softmax' | 'softplus' | 'softsign' | 'swish' | 'tanh'): Activation nonlinearity
            (<span style="color:#00C000"><b>default</b></span>: none).
        dropout (parameter, 0.0 <= float < 1.0): Dropout rate
            (<span style="color:#00C000"><b>default</b></span>: 0.0).
        vars_trainable (bool): Whether layer variables are trainable
            (<span style="color:#00C000"><b>default</b></span>: true).
        summary_labels ('all' | iter[string]): Labels of summaries to record
            (<span style="color:#00C000"><b>default</b></span>: inherit value of parent module).
        l2_regularization (float >= 0.0): Scalar controlling L2 regularization
            (<span style="color:#00C000"><b>default</b></span>: inherit value of parent module).
        name (string): Layer name
            (<span style="color:#00C000"><b>default</b></span>: internally chosen).
        input_spec (specification): <span style="color:#00C000"><b>internal use</b></span>.
        kwargs: Additional arguments for Keras LSTM layer, see
            `TensorFlow docs <https://www.tensorflow.org/api_docs/python/tf/keras/layers/LSTMCell>`__.
    """

    def __init__(
        self, size, horizon, bias=False, activation=None, dropout=0.0, vars_trainable=True,
        summary_labels=None, l2_regularization=None, name=None, input_spec=None, **kwargs
    ):
        super().__init__(
            cell='lstm', size=size, horizon=horizon, bias=bias, activation=activation,
            dropout=dropout, vars_trainable=vars_trainable, summary_labels=summary_labels,
            l2_regularization=l2_regularization, name=name, input_spec=input_spec, **kwargs
        )
