import gymnasium as gym
import torch
from lightning import Fabric
from omegaconf import DictConfig

from sheeprl.algos.ppo.agent import PPOAgent


@torch.no_grad()
def test(agent: PPOAgent, env: gym.Env, fabric: Fabric, cfg: DictConfig):
    agent.eval()
    done = False
    cumulative_rew = 0
    o = env.reset(seed=cfg.seed)[0]
    obs = {}
    for k in o.keys():
        if k in cfg.mlp_keys.encoder + cfg.cnn_keys.encoder:
            torch_obs = torch.from_numpy(o[k]).to(fabric.device).unsqueeze(0)
            if k in cfg.cnn_keys.encoder:
                torch_obs = torch_obs.reshape(1, -1, *torch_obs.shape[-2:]) / 255 - 0.5
            if k in cfg.mlp_keys.encoder:
                torch_obs = torch_obs.float()
            obs[k] = torch_obs

    while not done:
        # Act greedly through the environment
        if agent.is_continuous:
            actions = torch.cat(agent.get_greedy_actions(obs), dim=-1)
        else:
            actions = torch.cat([act.argmax(dim=-1) for act in agent.get_greedy_actions(obs)], dim=-1)

        # Single environment step
        o, reward, done, truncated, _ = env.step(actions.cpu().numpy().reshape(env.action_space.shape))
        done = done or truncated
        cumulative_rew += reward
        obs = {}
        for k in o.keys():
            if k in cfg.mlp_keys.encoder + cfg.cnn_keys.encoder:
                torch_obs = torch.from_numpy(o[k]).to(fabric.device).unsqueeze(0)
                if k in cfg.cnn_keys.encoder:
                    torch_obs = torch_obs.reshape(1, -1, *torch_obs.shape[-2:]) / 255 - 0.5
                if k in cfg.mlp_keys.encoder:
                    torch_obs = torch_obs.float()
                obs[k] = torch_obs

        if cfg.dry_run:
            done = True
    fabric.print("Test - Reward:", cumulative_rew)
    fabric.log_dict({"Test/cumulative_reward": cumulative_rew}, 0)
    env.close()
