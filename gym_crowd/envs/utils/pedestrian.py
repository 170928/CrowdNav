from gym_crowd.envs.utils.agent import Agent
from gym_crowd.envs.utils.state import JointState


class Pedestrian(Agent):
    def __init__(self, config, section):
        super().__init__(config, section)

    def act(self, ob):
        """
        The state for pedestrian is its full state and all other agents' observable states
        :param ob:
        :return:
        """
        state = JointState(self.get_full_state(), ob)
        action = self.policy.predict(state)
        return action
