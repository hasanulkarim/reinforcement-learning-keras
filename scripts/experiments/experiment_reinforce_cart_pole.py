"""Train and few DeepQAgents, plot the results, and run an episode on the best agent."""
from rlk.agents.components.helpers.virtual_gpu import VirtualGPU
from rlk.agents.policy_gradient.reinforce_agent import ReinforceAgent
from rlk.environments.cart_pole.cart_pole_config import CartPoleConfig
from rlk.experiment.agent_experiment import AgentExperiment


def run_exp(n_episodes: int = 1000, max_episode_steps: int = 500):
    exp = AgentExperiment(agent_class=ReinforceAgent,
                          agent_config=CartPoleConfig(agent_type='reinforce'),
                          n_reps=5,
                          n_jobs=6,
                          training_options={"n_episodes": n_episodes,
                                            "max_episode_steps": max_episode_steps,
                                            "update_every": 1})

    exp.run()
    exp.save(fn=f"{ReinforceAgent.__name__}_experiment.pkl")


if __name__ == "__main__":
    run_exp(n_episodes=1000)
