from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler


@dataclass(slots=True)
class Genome:
    mask: np.ndarray
    hidden_layer_size: int
    activation: str
    learning_rate_init: float


class HybridTrendPredictor:
    def __init__(self, population_size: int = 24, generations: int = 12, random_state: int = 42) -> None:
        self.population_size = population_size
        self.generations = generations
        self.random_state = random_state
        self.feature_columns = [
            "Return",
            "SMA_10",
            "SMA_20",
            "EMA_10",
            "EMA_20",
            "Momentum_5",
            "Volatility",
            "RSI",
            "MACD",
            "Signal_Line",
            "Volume_Trend",
        ]

    def fit_predict(self, frame: pd.DataFrame) -> dict[str, Any]:
        split_index = int(len(frame) * 0.8)
        training = frame.iloc[:split_index].copy()
        testing = frame.iloc[split_index:].copy()

        x_train = training[self.feature_columns].to_numpy()
        y_train = training["Target"].to_numpy()
        x_test = testing[self.feature_columns].to_numpy()
        y_test = testing["Target"].to_numpy()

        best_genome = self._run_genetic_search(x_train, y_train, x_test, y_test)
        selected_train = x_train[:, best_genome.mask]
        selected_test = x_test[:, best_genome.mask]

        scaler = StandardScaler()
        scaled_train = scaler.fit_transform(selected_train)
        scaled_test = scaler.transform(selected_test)

        model = MLPClassifier(
            hidden_layer_sizes=(best_genome.hidden_layer_size,),
            activation=best_genome.activation,
            learning_rate_init=best_genome.learning_rate_init,
            max_iter=700,
            random_state=self.random_state,
        )
        model.fit(scaled_train, y_train)
        predictions = model.predict(scaled_test)
        probabilities = model.predict_proba(scaled_test)[:, 1]
        accuracy = accuracy_score(y_test, predictions)
        precision = precision_score(y_test, predictions, zero_division=0)
        recall = recall_score(y_test, predictions, zero_division=0)
        f1 = f1_score(y_test, predictions, zero_division=0)
        matrix = confusion_matrix(y_test, predictions, labels=[0, 1]).tolist()

        latest_probability = float(probabilities[-1])
        latest_prediction = int(predictions[-1])
        return {
            "prediction": latest_prediction,
            "probability": latest_probability,
            "accuracy": float(accuracy),
            "precision": float(precision),
            "recall": float(recall),
            "f1_score": float(f1),
            "confusion_matrix": matrix,
            "best_genome": {
                "hidden_layer_size": best_genome.hidden_layer_size,
                "activation": best_genome.activation,
                "learning_rate_init": best_genome.learning_rate_init,
                "selected_features": [name for name, flag in zip(self.feature_columns, best_genome.mask) if flag],
            },
            "training_samples": len(training),
            "test_samples": len(testing),
            "train_split": 0.8,
        }

    def latest_feature_snapshot(self, frame: pd.DataFrame) -> dict[str, float]:
        latest_row = frame.iloc[-1]
        return {column: round(float(latest_row[column]), 5) for column in self.feature_columns}

    def _run_genetic_search(
        self, x_train: np.ndarray, y_train: np.ndarray, x_test: np.ndarray, y_test: np.ndarray
    ) -> Genome:
        rng = np.random.default_rng(self.random_state)
        population = [self._random_genome(rng) for _ in range(self.population_size)]

        for _ in range(self.generations):
            scored_population = sorted(
                ((self._fitness(genome, x_train, y_train, x_test, y_test), genome) for genome in population),
                key=lambda item: item[0],
                reverse=True,
            )
            survivors = [genome for _, genome in scored_population[: max(2, self.population_size // 3)]]
            offspring: list[Genome] = survivors.copy()
            while len(offspring) < self.population_size:
                parent_a, parent_b = rng.choice(survivors, size=2, replace=True)
                child = self._crossover(parent_a, parent_b, rng)
                offspring.append(self._mutate(child, rng))
            population = offspring

        return max(population, key=lambda genome: self._fitness(genome, x_train, y_train, x_test, y_test))

    def _fitness(
        self, genome: Genome, x_train: np.ndarray, y_train: np.ndarray, x_test: np.ndarray, y_test: np.ndarray
    ) -> float:
        if not genome.mask.any():
            return 0.0

        selected_train = x_train[:, genome.mask]
        selected_test = x_test[:, genome.mask]

        scaler = StandardScaler()
        scaled_train = scaler.fit_transform(selected_train)
        scaled_test = scaler.transform(selected_test)

        model = MLPClassifier(
            hidden_layer_sizes=(genome.hidden_layer_size,),
            activation=genome.activation,
            learning_rate_init=genome.learning_rate_init,
            max_iter=400,
            random_state=self.random_state,
        )
        model.fit(scaled_train, y_train)
        predictions = model.predict(scaled_test)
        accuracy = accuracy_score(y_test, predictions)
        feature_bonus = genome.mask.sum() / len(genome.mask)
        return float(accuracy - (feature_bonus * 0.05))

    def _random_genome(self, rng: np.random.Generator) -> Genome:
        mask = rng.integers(0, 2, len(self.feature_columns)).astype(bool)
        if not mask.any():
            mask[rng.integers(0, len(mask))] = True
        return Genome(
            mask=mask,
            hidden_layer_size=int(rng.choice([16, 24, 32, 48, 64])),
            activation=str(rng.choice(["relu", "tanh"])),
            learning_rate_init=float(rng.choice([0.0005, 0.001, 0.003, 0.005])),
        )

    @staticmethod
    def _crossover(parent_a: Genome, parent_b: Genome, rng: np.random.Generator) -> Genome:
        pivot = int(rng.integers(1, len(parent_a.mask)))
        mask = np.concatenate([parent_a.mask[:pivot], parent_b.mask[pivot:]])
        if not mask.any():
            mask[rng.integers(0, len(mask))] = True
        return Genome(
            mask=mask,
            hidden_layer_size=parent_a.hidden_layer_size if rng.random() > 0.5 else parent_b.hidden_layer_size,
            activation=parent_a.activation if rng.random() > 0.5 else parent_b.activation,
            learning_rate_init=(
                parent_a.learning_rate_init if rng.random() > 0.5 else parent_b.learning_rate_init
            ),
        )

    @staticmethod
    def _mutate(genome: Genome, rng: np.random.Generator) -> Genome:
        mask = genome.mask.copy()
        for index in range(len(mask)):
            if rng.random() < 0.08:
                mask[index] = ~mask[index]
        if not mask.any():
            mask[rng.integers(0, len(mask))] = True
        hidden_layer_size = genome.hidden_layer_size
        if rng.random() < 0.15:
            hidden_layer_size = int(rng.choice([16, 24, 32, 48, 64]))
        activation = genome.activation
        if rng.random() < 0.10:
            activation = str(rng.choice(["relu", "tanh"]))
        learning_rate_init = genome.learning_rate_init
        if rng.random() < 0.15:
            learning_rate_init = float(rng.choice([0.0005, 0.001, 0.003, 0.005]))
        return Genome(mask, hidden_layer_size, activation, learning_rate_init)
