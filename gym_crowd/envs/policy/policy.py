import numpy as np
import abc


class Policy(object):
    def __init__(self):
        ...

    @abc.abstractmethod
    def configure(self, config):
        ...

    @abc.abstractmethod
    def predict(self, state):
        """
        Policy takes state as input and output an action

        """
        ...

    @staticmethod
    def reach_destination(state):
        self_state = state.self_state
        if np.linalg.norm((self_state.py - self_state.gy, self_state.px - self_state.gx)) < self_state.radius:
            return True
        else:
            return False
