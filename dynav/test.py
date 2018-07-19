import torch
import logging
import argparse
import configparser
import gym
from dynav.utils.navigator import Navigator
from dynav.utils.explorer import Explorer
from dynav.policy.policy_factory import policy_factory


def main():
    parser = argparse.ArgumentParser('Parse configuration file')
    parser.add_argument('--env_config', type=str, default='configs/env.config')
    parser.add_argument('--policy', type=str, default='orca')
    parser.add_argument('--policy_config', type=str, default='configs/policy.config')
    parser.add_argument('--weights', type=str)
    parser.add_argument('--gpu', default=False, action='store_true')
    parser.add_argument('--visualize', default=False, action='store_true')
    parser.add_argument('--phase', type=str, default='test')
    parser.add_argument('--test_case', type=int, default=None)
    args = parser.parse_args()

    env_config = configparser.RawConfigParser()
    env_config.read(args.env_config)

    # configure policy
    policy = policy_factory[args.policy]()
    policy_config = configparser.RawConfigParser()
    policy_config.read(args.policy_config)
    policy.configure(policy_config)
    if policy.trainable:
        if args.weights is None:
            parser.error('Trainable policy must be specified with a saved weights')
        policy.get_model().load_state_dict(torch.load(args.weights))

    # configure device
    device = torch.device("cuda:0" if torch.cuda.is_available() and args.gpu else "cpu")
    logging.basicConfig(level=logging.INFO, format='%(asctime)s, %(levelname)s: %(message)s',
                        datefmt="%Y-%m-%d %H:%M:%S")
    logging.info('Using device: {}'.format(device))

    # configure environment
    env = gym.make('CrowdSim-v0')
    env.configure(env_config)
    navigator = Navigator(env_config, 'navigator')
    navigator.set_policy(policy)
    env.set_navigator(navigator)
    explorer = Explorer(env, navigator, device)

    policy.set_phase(args.phase)
    policy.set_device(device)
    if args.policy == 'value_network':
        policy.set_env(env)
        policy.set_epsilon(0.1)

    if args.visualize:
        ob = env.reset(args.phase, args.test_case)
        done = False
        while not done:
            action = navigator.act(ob)
            ob, reward, done, info = env.step(action)
        env.render('video')
        print('It takes {} steps to finish. Last step is {}'.format(env.timer, info))
    else:
        explorer.run_k_episodes(env.test_cases, args.phase)


if __name__ == '__main__':
    main()
