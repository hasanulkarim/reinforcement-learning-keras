"""Train and few DeepQAgents, plot the results, and run an episode on the best agent."""
from reinforcement_learning_keras.agents.components.helpers.virtual_gpu import VirtualGPU
from reinforcement_learning_keras.agents.q_learning.deep_q_agent import DeepQAgent
from reinforcement_learning_keras.environments.atari.space_invaders.space_invaders_config import SpaceInvadersConfig
from reinforcement_learning_keras.experiment.agent_experiment import AgentExperiment


def run_exp(agent_type: str, n_episodes: int = 3000, max_episode_steps: int = 10000):
    config = SpaceInvadersConfig(agent_type=agent_type, mode='stack')
    gpu = VirtualGPU(config.gpu_memory)

    exp = AgentExperiment(name=f"{agent_type} Space Invaders",
                          agent_class=DeepQAgent,
                          agent_config=config,
                          n_reps=2,
                          n_jobs=1 if gpu.on else 5,
                          training_options={"n_episodes": n_episodes,
                                            "verbose": 1,
                                            "max_episode_steps": max_episode_steps})

    exp.run()
    exp.save(fn=f"{DeepQAgent.__name__}_{agent_type}experiment.pkl")


if __name__ == "__main__":
    run_exp(agent_type='dqn')
    run_exp(agent_type='dueling_dqn')
    run_exp(agent_type='double_dqn')
    run_exp(agent_type='double_dueling_dqn')
