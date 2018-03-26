import numpy as np
import warnings
import time
import math
import random

warnings.filterwarnings("ignore")

from sklearn.base import clone
from mosaic.sklearn_mcts import mcts_model
from sklearn.pipeline import Pipeline
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.linear_model import LinearRegression


class EnsembleMTCS():
    def __init__(self, list_model_name, nb_play, nb_simulation, aggreg_score,
                 init_ressource, init_nb_child, nb_step_add_ressource, nb_step_to_add_nb_child,
                 ressource_to_add, number_child_to_add, start_time, acceleration, cv, info):
        self.list_model_name = list_model_name

        self.nb_play = nb_play
        self.nb_simulation = nb_simulation
        self.aggreg_score = aggreg_score
        self.init_ressource = init_ressource
        self.init_nb_child = init_nb_child
        self.nb_step_add_ressource = nb_step_add_ressource
        self.nb_step_to_add_nb_child = nb_step_to_add_nb_child
        self.ressource_to_add = ressource_to_add
        self.number_child_to_add = number_child_to_add
        self.best_final_score = 0

        self.start_time = start_time
        self.history_model = {}
        self.acceleration = acceleration
        self.bandits = [1000] * len(list_model_name)
        self.bandits_mean = [0] * len(list_model_name)
        self.nb_visits = [0] * len(list_model_name)
        self.cv = cv
        self.info = info

        if self.info["task"] == "binary.classification"
            self.stacking = LinearRegression(n_jobs=2)
        else:
            raise Exception("Can't handle task: {0}".format(self.info["task"]))

    def train(self, X, y, D=None):
        if X.shape[0] * 2 < X.shape[1]:
            high_dimensional_data = True
        else:
            high_dimensional_data = False

        models = {}
        for name in self.list_model_name:
            if name in ["RandomForestClassifier", "XGBClassifier", "LogisticRegression", "SGDClassifier"]:
                models[name] = mcts_model(name, X, y, self.nb_play, self.nb_simulation, self.aggreg_score,
                                          self.init_ressource, self.init_nb_child, self.nb_step_add_ressource,
                                          self.nb_step_to_add_nb_child,
                                          self.ressource_to_add, self.number_child_to_add, self.cv)
            else:
                models[name] = mcts_model(name, X, y, self.nb_play, self.nb_simulation * self.acceleration,
                                          self.aggreg_score,
                                          self.init_ressource, self.init_nb_child, self.nb_step_add_ressource,
                                          self.nb_step_to_add_nb_child,
                                          self.ressource_to_add, self.number_child_to_add, self.cv)
        begin_bandit = 1

        for i in range(self.nb_play):
            estimators = []
            is_not_new = []

            choosed_armed = np.argmax(self.bandits)
            print("Choosed: {0}: {1}".format(self.list_model_name[choosed_armed], self.bandits))
            if i < begin_bandit:
                for name in self.list_model_name:
                    p, statut, score = next(models[name])
                    estimators.append(self.create_pipeline(p))
                    is_not_new.append(statut)
            else:
                for index, name in enumerate(self.list_model_name):
                    if index == choosed_armed:
                        self.nb_visits[choosed_armed] += 1
                        p, statut, score = next(models[name])
                        estimators.append(self.create_pipeline(p))
                        is_not_new.append(statut)
                        if statut:
                            reward = 0
                        else:
                            reward = 1
                    else:
                        estimators.append(clone(self.history_model[index][0]))
                        is_not_new.append(True)

            scores = self.cross_validation_estimators(estimators, X, y, D, is_not_new)
            val_scores = self.aggreg_score(scores)

            if (
            not high_dimensional_data) and i >= begin_bandit and reward == 1 and score > val_scores and score > self.best_final_score:
                print("======> Play {0}: Score:{1}".format(i, score))
                print("Single estimator is better!")

                self.update_reward(choosed_armed, 1, i)

                self.best_final_score = score
                e = self.create_pipeline(p)
                e.fit(X, y)
                try:
                    val = e.predict_proba(D.data["X_valid"])[:, 1]
                    test = e.predict_proba(D.data["X_test"])[:, 1]
                except:
                    val = e.predict(D.data["X_valid"])
                    test = e.predict(D.data["X_test"])

                print("======> Best scores: {0}\n\n".format(self.best_final_score))
                yield val, test

            print("======> Play {0}: scores: {1} Score:{2}".format(i, scores, val_scores))
            print("======> Best scores: {0}\n\n".format(max(self.best_final_score, val_scores)))
            if i >= begin_bandit:
                self.update_reward(choosed_armed, int(val_scores > self.best_final_score), i)

            if self.best_final_score < val_scores:
                self.best_final_score = val_scores
                yield self.fit_predict(estimators, X, y, D)
            else:
                self.print_remaining_time(D)
                yield None, None

    def print_remaining_time(self, D):
        now = time.time()
        spend = now - self.start_time
        print("\n\n---------------------------------------------------------------")
        print("             Time elapsed: {0}         Remaining time: {1}".format(spend,
                                                                                  float(D.info['time_budget']) - spend))
        print("---------------------------------------------------------------\n\n")

    def update_reward(self, choosed_armed, reward, t):
        self.bandits_mean[choosed_armed] = self.bandits_mean[choosed_armed] + (
                    reward - self.bandits_mean[choosed_armed]) / self.nb_visits[choosed_armed]
        for i in range(len(self.bandits)):
            try:
                self.bandits[i] = self.bandits_mean[i] + math.sqrt(2 * math.log(t) / self.nb_visits[i])
            except:
                self.bandits[i] = 10000

    def fit_predict(self, estimators, X, y, D):
        train_stack = []
        y_valid = []
        y_test = []

        for e in estimators:
            e.fit(X, y)

            if self.info["task"] == "binary.classification":
                try:
                    train_stack_ = e.predict_proba(X)[:, 1]
                    y_valid_ = e.predict_proba(D.data["X_valid"])[:, 1]
                    y_test_ = e.predict_proba(D.data["X_test"])[:, 1]
                except:
                    train_stack_ = e.predict(X)
                    y_valid_ = e.predict(D.data["X_valid"])
                    y_test_ = e.predict(D.data["X_test"])
            else:
                raise Exception("Can't handle task: {0}".format(self.info["task"]))

            train_stack.append(train_stack_)
            y_valid.append(y_valid_)
            y_test.append(y_test_)

        train_stack = np.transpose(train_stack)
        y_valid = np.transpose(y_valid)
        y_test = np.transpose(y_test)

        final_valid = []
        final_test = []

        for stacking in self.list_stacking:
            final_valid.append(stacking.predict(y_valid))
            final_test.append(stacking.predict(y_test))

        final_valid = np.mean(np.transpose(final_valid), axis=1)
        final_test = np.mean(np.transpose(final_test), axis=1)

        final_valid[final_valid < 0] = 0
        final_valid[final_valid > 1] = 1
        final_test[final_test < 0] = 0
        final_test[final_test > 1] = 1
        return final_valid, final_test

    def cross_validation_estimators(self, estimators, X, y, D, is_not_new=[]):
        skf = StratifiedKFold(n_splits=self.cv, shuffle=False, random_state=42)
        scores = []

        n_fold = 0

        oof_y = []
        oof_train = []

        for train_index, test_index in skf.split(X, y):
            X_train, X_test = X[train_index], X[test_index]
            y_train, y_test = y[train_index], y[test_index]

            y_pred = []

            for index, e in enumerate(estimators):

                if is_not_new[index]:
                    e = self.history_model[index][n_fold]
                else:
                    e = clone(e)
                    e.fit(X_train, y_train)
                    if n_fold == 0:
                        self.history_model[index] = [e]
                    else:
                        self.history_model[index].append(e)

                try:
                    y_pred_ = e.predict_proba(X_test)[:, 1]
                except:
                    y_pred_ = e.predict(X_test)

                y_pred.append(y_pred_)

            y_pred = np.transpose(y_pred)

            oof_y.extend(y_test)

            if oof_train == []:
                oof_train = y_pred
            else:
                oof_train = np.concatenate([oof_train, y_pred], axis=0)

            n_fold += 1

        oof_train = np.array(oof_train)
        oof_y = np.array(oof_y)

        skf = StratifiedKFold(n_splits=self.cv, shuffle=False, random_state=43)
        scores = []

        self.list_stacking = []

        for train_index, test_index in skf.split(oof_train, oof_y):
            e = clone(self.stacking)
            X_train, X_test = oof_train[train_index], oof_train[test_index]
            y_train, y_test = oof_y[train_index], oof_y[test_index]

            with warnings.catch_warnings(record=True) as w:
                e.fit(X_train, y_train)

            self.list_stacking.append(e)

            if self.info["task"] == "binary.classification":
                y_final = e.predict(X_test)
                y_final[y_final < 0] = 0
                y_final[y_final > 1] = 1
                score = self.score_func(y_test, y_final)
            else:
                raise Exception("Can't handle task: {0}".format(self.info["task"]))

            scores.append(score)

        return scores

    def create_pipeline(self, res):
        pipeline = []
        preprocessing = res["preprocessing"]
        if preprocessing != None:
            pipeline.append(("preprocessing", preprocessing))

        pipeline.append(("estimator", clone(res["estimator"])))
        return Pipeline(pipeline)