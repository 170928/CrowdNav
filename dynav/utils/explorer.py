import logging
import torch
import copy


class Explorer(object):
    def __init__(self, env, navigator, device, memory=None, gamma=None, target_policy=None):
        self.env = env
        self.navigator = navigator
        self.device = device
        self.memory = memory
        self.gamma = gamma
        self.target_policy = target_policy
        self.stabilized_model = None

    def update_stabilized_model(self, stabilized_model):
        self.stabilized_model = copy.deepcopy(stabilized_model)

    # @profile
    def run_k_episodes(self, k, phase, update_memory=False, imitation_learning=False, episode=None, print_failure=False):
        self.navigator.policy.set_phase(phase)
        navigator_times = []
        avg_ped_times = []
        success = 0
        collision = 0
        timeout = 0
        collision_cases = []
        timeout_cases = []
        for i in range(k):
            ob = self.env.reset(phase)
            done = False
            states = []
            actions = []
            rewards = []
            while not done:
                action = self.navigator.act(ob)
                ob, reward, done, info = self.env.step(action)
                states.append(self.navigator.policy.last_state)
                actions.append(action)
                rewards.append(reward)

            if info == 'reach goal':
                success += 1
                navigator_times.append(self.env.global_time)
                if self.navigator.visible:
                    avg_ped_times.append(self.env.get_average_ped_time())
            elif info == 'collision':
                collision += 1
                collision_cases.append(i)
            elif info == 'timeout':
                timeout += 1
                timeout_cases.append(i)
            else:
                raise ValueError('Invalid info from environment')

            if update_memory:
                if (imitation_learning and info == 'reach goal') or \
                   (not imitation_learning and info in ['reach goal', 'collision']):
                    # only provide successful demonstrations in imitation learning
                    # only add positive(success) or negative(collision) experience in reinforcement learning
                    self.update_memory(states, actions, rewards, imitation_learning)

        success_rate = success / k
        collision_rate = collision / k
        assert success + collision + timeout == k
        if len(navigator_times) == 0:
            avg_nav_time = 0
        else:
            avg_nav_time = sum(navigator_times) / len(navigator_times)

        extra_info = '' if episode is None else 'in episode {} '.format(episode)
        logging.info('{:<5} {}has success rate: {:.2f}, collision rate: {:.2f}, average time to reach goal: {:.2f}'.
                     format(phase.upper(), extra_info, success_rate, collision_rate, avg_nav_time))
        if self.navigator.visible:
            if len(avg_ped_times) == 0:
                avg_ped_time = 0
            else:
                avg_ped_time = sum(avg_ped_times) / len(avg_ped_times)
            logging.info('Average time for peds to reach goal: {:.2f}'.format(avg_ped_time))

        if print_failure:
            logging.info('Collision cases: ' + ' '.join([str(x) for x in collision_cases]))
            logging.info('Timeout cases: ' + ' '.join([str(x) for x in timeout_cases]))

    def update_memory(self, states, actions, rewards, imitation_learning=False):
        if self.memory is None or self.gamma is None:
            raise ValueError('Memory or gamma value is not set!')

        for i in range(len(states)):
            state = states[i]
            reward = rewards[i]

            if imitation_learning:
                # in imitation learning, the value of state is defined based on the time to reach the goal
                state = self.target_policy.transform(state)
                value = pow(self.gamma, (len(states) - 1 - i) * self.navigator.time_step * self.navigator.v_pref)
            else:
                if i == len(states) - 1:
                    # terminal state
                    value = reward
                else:
                    next_state = states[i + 1]
                    gamma_bar = pow(self.gamma, self.navigator.time_step * self.navigator.v_pref)
                    value = reward + gamma_bar * self.stabilized_model(next_state.unsqueeze(0)).data.item()
            value = torch.Tensor([value]).to(self.device)

            self.memory.push((state, value))
