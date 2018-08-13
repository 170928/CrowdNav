import logging
from gym_crowd.envs.utils.agent import Agent
from gym_crowd.envs.utils.state import JointState


class Navigator(Agent):
    def __init__(self, config, section):
        super().__init__(config, section)
        logging.info('Navigator is {}'.format('visible' if self.visible else 'invisible'))

    def set_policy(self, policy):
        self.policy = policy

    def act(self, ob):
        if self.policy is None:
            raise AttributeError('Policy attribute has to be set!')
        state = JointState(self.get_full_state(), ob)
        action = self.policy.predict(state)
        return action
