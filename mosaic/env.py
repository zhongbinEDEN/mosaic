"""Base environement class."""

from mosaic.space import Space
from mosaic.scenario import ListTask, ComplexScenario, ChoiceScenario

class Env():
    """Base class for environement."""

    terminal_state = []

    def __init__(self, scenario = None, sampler = {}):
        """Constructor."""
        self.bestconfig = {
            "score": 0,
            "model": None
        }
        self.space = Space(scenario = scenario, sampler = sampler)
        self.history = {}

    def rollout(self, history = []):
        return self.space.playout(history)

    def _preprocess_moves(self, list_moves, index):
        model = list_moves[index][0]
        param_model = {}
        last_index = index
        for i in range(index + 1, len(list_moves)):
            last_index = i
            config, val = list_moves[i]
            if config.startswith(model):
                param_model[config.split("__")[1]] = val
            else:
                break
        return  model, param_model, last_index

    def preprocess_moves(self, list_moves):
        index = 0
        preprocessed_moves = []
        while(index < len(list_moves) - 1):
            model, params, index = self._preprocess_moves(list_moves, index)
            preprocessed_moves.append((model, params))
        return preprocessed_moves

    def _evaluate(self, list_moves = []):
        config = self.preprocess_moves(list_moves)

        hash_moves = hash(tuple(a for a in config))
        if hash_moves in self.history:
            return self.history[hash_moves]

        res = self.evaluate(config)

        if res > self.bestconfig["score"]:
            self.bestconfig = {
                "score": res,
                "model": config
            }

        # Add into history
        self.history[hash_moves] = res
        return res

    def evaluate(self, config):
        """Method for moves evaluation."""
        return 0


def a_func(): return 0
def b_func(): return 0
def c_func(): return 0

x1 = ListTask(is_ordered=False, name = "x1", tasks = ["x1__p1", "x1__p2"])
x2 = ListTask(is_ordered=True, name = "x2",  tasks = ["x2__p1", "x2__p2"])

start = ChoiceScenario(name = "Model", scenarios=[x1, x2])

sampler = { "x1__p1": ([0, 1], "uniform", "float"),
            "x1__p2": ([[1, 2, 3, 4, 5, 6, 7]], "choice", "int"),
            "x2__p1": ([["a", "b", "c", "d"]], "choice", "string"),
            "x2__p2": ([[a_func, b_func, c_func]], "choice", "func"),
}

space = Space(scenario = start, sampler = sampler)
ex_config = space.playout(history=[("Model", None)])

env = Env(scenario = start, sampler = sampler)
env.preprocess_moves(ex_config)
