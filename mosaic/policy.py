"""Policy for bandit phase."""


import random
import math


class UCT():
    """Implements the UCT algorithm."""

    def BESTCHILD(self, node, scalar):
        """Return the best child."""
        bestscore = 0.0
        bestchildren = []
        for c in node.children:
            score = self.uct(node, c, scalar)
            if score == bestscore:
                bestchildren.append(c)
            if score > bestscore:
                bestchildren = [c]
                bestscore = score
        if len(bestchildren) == 0:
            print("OOPS: no best child found, probably fatal")
            # raise Exception("No best child found")
            random.choice([c for c in node.children])
        return random.choice(bestchildren)

    def uct(self, node, c, scalar):
        """Calculate value of node."""
        exploit = c.reward / c.visits
        if float(c.visits) == 0:
            explore = 1000
        else:
            explore = math.sqrt(2.0 * math.log(node.visits) / float(c.visits))
        score = exploit + (scalar * explore)
        return score