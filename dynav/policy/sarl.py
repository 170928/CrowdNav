import numpy as np
import torch
import torch.nn as nn
from torch.nn.functional import softmax
import logging
from dynav.policy.cadrl import mlp
from dynav.policy.multi_ped_rl import MultiPedRL


class ValueNetwork(nn.Module):
    def __init__(self, input_dim, self_state_dim, mlp1_dims, mlp2_dims, mlp3_dims, attention_dims, with_global_state,
                 global_om, cell_size, cell_num):
        super().__init__()
        self.self_state_dim = self_state_dim
        self.global_state_dim = mlp1_dims[-1]
        self.mlp1 = mlp(input_dim, mlp1_dims, last_relu=True)
        self.mlp2 = mlp(mlp1_dims[-1], mlp2_dims)
        self.with_global_state = with_global_state
        if with_global_state:
            self.attention = mlp(mlp1_dims[-1] * 2, attention_dims)
        else:
            self.attention = mlp(mlp1_dims[-1], attention_dims)
        self.global_om = global_om
        self.cell_size = cell_size
        self.cell_num = cell_num
        mlp3_input_dim = mlp2_dims[-1] + self.self_state_dim + (cell_num ** 2 if global_om else 0)
        self.mlp3 = mlp(mlp3_input_dim, mlp3_dims)
        self.attention_weights = None

    def forward(self, state):
        """
        First transform the world coordinates to self-centric coordinates and then do forward computation

        :param state: tensor of shape (batch_size, # of peds, length of a rotated state)
        :return:
        """
        size = state.shape
        self_state = state[:, 0, :self.self_state_dim]
        mlp1_output = self.mlp1(torch.reshape(state, (-1, size[2])))
        mlp2_output = self.mlp2(mlp1_output)
        if True:
            global_om = self.build_global_om(state)

        if self.with_global_state:
            # compute attention scores
            global_state = torch.mean(torch.reshape(mlp1_output, (size[0], size[1], -1)), 1, keepdim=True)
            global_state = torch.reshape(global_state.expand((size[0], size[1], self.global_state_dim)),
                                         (-1, self.global_state_dim))
            attention_input = torch.cat([mlp1_output, global_state], dim=1)
        else:
            attention_input = mlp1_output
        scores = torch.reshape(self.attention(attention_input), (size[0], size[1], 1)).squeeze(dim=2)
        weights = softmax(scores, dim=1).unsqueeze(2)
        self.attention_weights = weights[0, :, 0].data.cpu().numpy()

        # output feature is a linear combination of input features
        features = torch.reshape(mlp2_output, (size[0], size[1], -1))
        weighted_feature = torch.sum(weights.expand_as(features) * features, dim=1)

        # concatenate agent's state with global weighted peds' state
        if self.global_om:
            joint_state = torch.cat([self_state, weighted_feature, global_om], dim=1)
        else:
            joint_state = torch.cat([self_state, weighted_feature], dim=1)
        value = self.mlp3(joint_state)
        return value

    def build_global_om(self, state):
        """

        :param state: (batch_size, ped_num, state_len)
        :return:
        """
        x_index = torch.floor(state[:, :, 6] / self.cell_size + self.cell_num / 2)
        y_index = torch.floor(state[:, :, 7] / self.cell_size + self.cell_num / 2)
        x_index[x_index < 0] = float('-inf')
        x_index[x_index >= self.cell_num] = float('-inf')
        y_index[y_index < 0] = float('-inf')
        y_index[y_index >= self.cell_num] = float('-inf')
        grid_indices = (self.cell_num * y_index + x_index).cpu().numpy()
        oms = []
        for ped in range(grid_indices.shape[0]):
            om = np.isin(range(self.cell_num ** 2), grid_indices[ped, :]).astype(float)
            oms.append([om])
        occupancy_map = np.concatenate(oms, axis=0)
        return torch.from_numpy(occupancy_map).float()


class SARL(MultiPedRL):
    def __init__(self):
        super().__init__()
        self.name = 'SARL'

    def configure(self, config):
        self.set_common_parameters(config)
        mlp1_dims = [int(x) for x in config.get('sarl', 'mlp1_dims').split(', ')]
        mlp2_dims = [int(x) for x in config.get('sarl', 'mlp2_dims').split(', ')]
        mlp3_dims = [int(x) for x in config.get('sarl', 'mlp3_dims').split(', ')]
        attention_dims = [int(x) for x in config.get('sarl', 'attention_dims').split(', ')]
        self.with_om = config.getboolean('sarl', 'with_om')
        with_global_state = config.getboolean('sarl', 'with_global_state')
        with_global_om = config.getboolean('sarl', 'with_global_om')
        self.model = ValueNetwork(self.input_dim(), self.self_state_dim, mlp1_dims, mlp2_dims, mlp3_dims,
                                  attention_dims, with_global_state, with_global_om, self.cell_size, self.cell_num)
        self.multiagent_training = config.getboolean('sarl', 'multiagent_training')
        if self.with_om:
            self.name = 'OM-SARL'
        logging.info('Policy: {} {} global state'.format(self.name, 'w/' if with_global_state else 'w/o'))

    def get_attention_weights(self):
        return self.model.attention_weights
