# DyNav
Robot navigation in a dynamic environment


## Usage


## Details
### Environment
There are n pedestrians in the scene with unknown policies A1, A2, ...,
An and one agent with know policy B. Unknown polices can be linear, random,
ORCA or following the exact trajectories in trajnet)

### Agent
* Agent is controlled by policy B, which is the policy we want to learn
and optimize. Policy could be hand-crafted rule like ORCA or a learned
policy like RL.
* Agent can have either the visual perception or the coordinate input.
* Agent is invisible if the pedestrian policies are following trajnet.


### Evaluation
Both the collision rate and extra time to reach goal are used to measure
the methods.
