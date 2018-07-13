import torch
import torch.nn as nn
import numpy as np
import random
import itertools
from gym_crowd.envs.policy.policy import Policy
from gym_crowd.envs.utils.action import ActionRot, ActionXY
from gym_crowd.envs.utils.state import ObservableState, FullState


class IndexTranslator(object):
    def __init__(self, state):
        self.state = state
        self.px = self.state[:, 0].reshape(-1, 1)
        self.py = self.state[:, 1].reshape(-1, 1)
        self.vx = self.state[:, 2].reshape(-1, 1)
        self.vy = self.state[:, 3].reshape(-1, 1)
        self.radius = self.state[:, 4].reshape(-1, 1)
        self.gx = self.state[:, 5].reshape(-1, 1)
        self.gy = self.state[:, 6].reshape(-1, 1)
        self.v_pref = self.state[:, 7].reshape(-1, 1)
        self.theta = self.state[:, 8].reshape(-1, 1)
        self.px1 = self.state[:, 9].reshape(-1, 1)
        self.py1 = self.state[:, 10].reshape(-1, 1)
        self.vx1 = self.state[:, 11].reshape(-1, 1)
        self.vy1 = self.state[:, 12].reshape(-1, 1)
        self.radius1 = self.state[:, 13].reshape(-1, 1)


class ValueNetwork(nn.Module):
    def __init__(self, reparameterization, state_dim, kinematics, fc_layers):
        super().__init__()
        self.reparameterization = reparameterization
        self.state_dim = state_dim
        self.kinematics = kinematics
        self.fc_layers = fc_layers
        self.value_network = nn.Sequential(nn.Linear(state_dim, fc_layers[0]), nn.ReLU(),
                                           nn.Linear(fc_layers[0], fc_layers[1]), nn.ReLU(),
                                           nn.Linear(fc_layers[1], fc_layers[2]), nn.ReLU(),
                                           nn.Linear(fc_layers[2], 1))

    def rotate(self, state):
        # first translate the coordinate then rotate around the origin
        # 'px', 'py', 'vx', 'vy', 'radius', 'gx', 'gy', 'v_pref', 'theta', 'px1', 'py1', 'vx1', 'vy1', 'radius1'
        #  0     1      2     3      4        5     6         7        8       9      10     11    12       13
        state = IndexTranslator(state.cpu().numpy())
        dx = state.gx - state.px
        dy = state.gy - state.py
        rot = np.arctan2(state.gy-state.py, state.gx-state.px)

        dg = np.linalg.norm(np.concatenate([dx, dy], axis=1), axis=1, keepdims=True)
        v_pref = state.v_pref
        vx = state.vx * np.cos(rot) + state.vy * np.sin(rot)
        vy = state.vy * np.cos(rot) - state.vx * np.sin(rot)
        radius = state.radius
        if self.kinematics == 'unicycle':
            theta = state.theta - rot
        else:
            theta = state.theta
        vx1 = state.vx1 * np.cos(rot) + state.vy1 * np.sin(rot)
        vy1 = state.vy1 * np.cos(rot) - state.vx1 * np.sin(rot)
        px1 = (state.px1 - state.px) * np.cos(rot) + (state.py1 - state.py) * np.sin(rot)
        py1 = (state.py1 - state.py) * np.cos(rot) - (state.px1 - state.px) * np.sin(rot)
        radius1 = state.radius1
        radius_sum = radius + radius1
        cos_theta = np.cos(theta)
        sin_theta = np.sin(theta)
        da = np.linalg.norm(np.concatenate([state.px - state.px1, state.py - state.py1], axis=1), axis=1, keepdims=True)

        new_state = np.concatenate([dg, v_pref, vx, vy, radius, theta, vx1, vy1, px1, py1,
                                    radius1, radius_sum, cos_theta, sin_theta, da], axis=1)
        return torch.Tensor(new_state)

    def forward(self, state, device):
        if self.reparameterization:
            state = self.rotate(state)
        value = self.value_network(state.to(device))
        return value


class ValueNetworkPolicy(Policy):
    def __init__(self):
        super().__init__()
        self.trainable = True
        self.kinematics = None
        self.value_network = None
        self.discrete = None
        self.action_space = None
        # TODO: modify the code and remove the environment
        self.env = None
        self.epsilon = None
        self.phase = None
        self.gamma = None
        self.device = None
        self.state = None

    def configure(self, config):
        reparameterization = config.getboolean('value_network', 'reparameterization')
        state_dim = config.getint('value_network', 'state_dim')
        fc_layers = [int(x) for x in config.get('value_network', 'fc_layers').split(', ')]
        self.kinematics = config.get('value_network', 'kinematics')
        self.value_network = ValueNetwork(reparameterization, state_dim, self.kinematics, fc_layers)
        self.gamma = config.getfloat('value_network', 'gamma')
        self.discrete = config.getboolean('value_network', 'discrete')

        # check if parameters are valid
        if reparameterization:
            assert state_dim == 15
        assert self.kinematics in ['holonomic', 'unicycle']

    def set_env(self, env):
        self.env = env

    def set_epsilon(self, epsilon):
        self.epsilon = epsilon

    def set_phase(self, phase):
        self.phase = phase

    def set_device(self, device):
        self.device = device

    def get_model(self):
        return self.value_network

    def get_state(self):
        return self.state

    def build_action_space(self, v_pref):
        """
        Action space consists of 25 precomputed actions and 10 randomly sampled actions.
        """
        if self.kinematics == 'unicycle':
            velocities = [(i + 1) / 5 * v_pref for i in range(5)]
            rotations = [i / 4 * np.pi / 3 - np.pi / 6 for i in range(5)]
            action_space = [ActionRot(*x) for x in itertools.product(velocities, rotations)]
            for i in range(25):
                random_velocity = random.random() * v_pref
                random_rotation = random.random() * np.pi / 3 - np.pi / 6
                action_space.append(ActionRot(random_velocity, random_rotation))
            action_space.append(ActionRot(0, 0))
        else:
            vxs = [(i + 1) / 5 * v_pref for i in range(5)]
            vys = [(i + 1) / 5 * v_pref for i in range(5)]
            action_space = [ActionXY(*x) for x in itertools.product(vxs, vys)]
            for i in range(25):
                random_vx = random.random() * v_pref
                random_vy = random.random() * v_pref
                action_space.append(ActionXY(random_vx, random_vy))
            action_space.append(ActionXY(0, 0))

        return action_space

    def propagate(self, state, action):
        delta_t = 1
        if isinstance(state, ObservableState):
            # propagate state of peds
            new_px = state.px + action.vx * delta_t
            new_py = state.py + action.vy * delta_t
            state = ObservableState(new_px, new_py, action.vx, action.vy, state.radius)
        elif isinstance(state, FullState):
            # propagate state of current agent
            # perform action without rotation
            if self.kinematics == 'holonomic':
                new_px = state.px + action.vx * delta_t
                new_py = state.py + action.vy * delta_t
            else:
                new_px = state.px + np.cos(action.r + state.theta) * action.v * delta_t
                new_py = state.py + np.sin(action.r + state.theta) * action.v * delta_t
            state = FullState(new_px, new_py, state.vx, state.vy, state.radius,
                              state.gx, state.gy, state.v_pref, state.theta)
        else:
            raise ValueError('Type error')

        return state

    def predict(self, state):
        """
        Input state is the full state of navigator plus the observable state of other agents

        """
        if self.action_space is None:
            self.action_space = self.build_action_space(state.self_state.v_pref)

        probability = random.random()
        if self.phase == 'train' and probability < self.epsilon:
            max_action = random.choice(self.action_space)
        else:
            max_min_value = float('-inf')
            max_action = None
            for action in self.action_space:
                min_value = float('inf')
                min_state = None
                for ped_state in state.ped_states:
                    next_self_state = self.propagate(state.self_state, action)
                    next_ped_state = self.propagate(ped_state, ActionXY(ped_state.vx, ped_state.vy))
                    joint_state = torch.Tensor([next_self_state + next_ped_state]).to(self.device)
                    value = self.env.reward(action) + pow(self.gamma, state.self_state.v_pref) * \
                            self.value_network(joint_state, self.device).data.item()
                    if value < min_value:
                        min_value = value
                        min_state = joint_state
                if min_value > max_min_value:
                    max_min_value = min_value
                    max_action = action
                    self.state = min_state

        return max_action
