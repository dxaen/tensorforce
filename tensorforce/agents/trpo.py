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

from tensorforce.agents import PolicyAgent


class TrustRegionPolicyOptimization(PolicyAgent):
    """
    [Trust Region Policy Optimization](https://arxiv.org/abs/1502.05477) agent (specification key:
    `trpo`).
    """

    def __init__(
        # Environment
        self, states, actions, max_episode_timesteps,
        # Network
        network='auto',
        # Optimization
        batch_size=10, update_frequency=None, learning_rate=1e-3,
        # Reward estimation
        likelihood_ratio_clipping=0.2, discount=0.99, estimate_terminal=True,
        # Critic
        critic_network=None, critic_optimizer=None,
        # Preprocessing
        preprocessing=None,
        # Exploration
        exploration=0.0, variable_noise=0.0,
        # Regularization
        l2_regularization=0.0, entropy_regularization=0.0,
        # TensorFlow etc
        name='agent', device=None, parallel_interactions=1, seed=None, execution=None, saver=None,
        summarizer=None
    ):
        memory = dict(type='recent', capacity=((batch_size + 1) * max_episode_timesteps))
        if update_frequency is None:
            update = dict(unit='episodes', batch_size=batch_size)
        else:
            update = dict(unit='episodes', batch_size=batch_size, frequency=update_frequency)
        optimizer = dict(
            type='natural_gradient', learning_rate=learning_rate, cg_max_iterations=10,
            cg_damping=1e-3
        )
        optimizer = dict(
            type='optimized_step', optimizer=optimizer, ls_max_iterations=10, ls_accept_ratio=0.9,
            ls_mode='exponential',  # !!!!!!!!!!!!!
            ls_parameter=0.5,  # !!!!!!!!!!!!!
        )
        objective = dict(
            type='policy_gradient', ratio_based=True, clipping_value=likelihood_ratio_clipping
        )
        if critic_network is None:
            reward_estimation = dict(horizon='episode', discount=discount)
        else:
            reward_estimation = dict(
                horizon='episode', discount=discount,
                estimate_horizon=('late' if estimate_terminal else False),
                estimate_terminal=estimate_terminal, estimate_advantage=True
            )
        if critic_network is None:
            baseline_objective = None
        else:
            baseline_objective = 'state_value'
            assert critic_optimizer is not None

        super().__init__(
            # Agent
            states=states, actions=actions, max_episode_timesteps=max_episode_timesteps,
            parallel_interactions=parallel_interactions, buffer_observe=max_episode_timesteps,
            seed=seed,
            # Model
            name=name, device=device, execution=execution, saver=saver, summarizer=summarizer,
            preprocessing=preprocessing, exploration=exploration, variable_noise=variable_noise,
            l2_regularization=l2_regularization,
            # PolicyModel
            policy=None, network=network, memory=memory, update=update, optimizer=optimizer,
            objective=objective, reward_estimation=reward_estimation, baseline_policy=None,
            baseline_network=critic_network, baseline_objective=baseline_objective,
            baseline_optimizer=critic_optimizer, entropy_regularization=entropy_regularization
        )
