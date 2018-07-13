from gym_crowd.envs.policy.policy import Policy
from gym_crowd.envs.utils.action import ActionXY
import numpy as np


class LinearPolicy(Policy):
    def __init__(self):
        super().__init__()
        self.trainable = False

    def predict(self, state, kinematics):
        assert kinematics == 'holonomic'

        self_state = state.self_state
        theta = np.arctan2(self_state.gy-self_state.py, self_state.gx-self_state.px)
        vx = np.cos(theta) * self_state.v_pref
        vy = np.sin(theta) * self_state.v_pref
        action = ActionXY(vx, vy)

        return action
