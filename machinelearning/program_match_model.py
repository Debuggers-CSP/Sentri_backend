from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple
import numpy as np
from sklearn.tree import DecisionTreeClassifier

@dataclass(frozen=True)
class ProgramMatchConfig:
    # Expanded features to distinguish between specific programs
    feature_names: Tuple[str, ...] = (
        "is_substance_abuse",
        "is_family_member",
        "has_trauma",
        "is_minor",
        "is_behavioral_issue",
        "focus_alcohol",       # New: to distinguish AA
        "focus_drugs",         # New: to distinguish NA
        "focus_cocaine",       # New: to distinguish CA
        "focus_gambling",      # New: to distinguish GA
        "focus_sex_rel"        # New: to distinguish SA
    )
    program_ids: Tuple[str, ...] = ("AA", "ACA", "Alateen", "Al-Anon", "NA", "CA", "GA", "SA")

class ProgramMatchModel:
    def __init__(self, random_state: int = 42) -> None:
        self.config = ProgramMatchConfig()
        # Increased depth and better training data
        self.classifier = DecisionTreeClassifier(max_depth=10, random_state=random_state)
        x_train, y_train = self.generate_archetype_training_data()
        self.classifier.fit(x_train, y_train)

    def generate_archetype_training_data(self):
        """Generates clean, non-random archetypes for the tree to learn correctly."""
        x_data = []
        y_data = []

        # Archetype Mapping: [sub, fam, traum, minor, behav, alc, drug, coke, gamb, sex]
        archetypes = [
            ([1, 0, 0, 0, 0, 1, 0, 0, 0, 0], "AA"),      # Alcohol focus -> AA
            ([1, 0, 0, 0, 0, 0, 1, 0, 0, 0], "NA"),      # Drug focus -> NA
            ([1, 0, 0, 0, 0, 0, 0, 1, 0, 0], "CA"),      # Cocaine focus -> CA
            ([0, 0, 0, 0, 1, 0, 0, 0, 1, 0], "GA"),      # Gambling focus -> GA
            ([0, 0, 0, 0, 1, 0, 0, 0, 0, 1], "SA"),      # Sex/Relationship focus -> SA
            ([0, 1, 1, 0, 0, 0, 0, 0, 0, 0], "ACA"),     # Family + Trauma -> ACA
            ([0, 1, 0, 1, 0, 0, 0, 0, 0, 0], "Alateen"), # Family + Minor -> Alateen
            ([0, 1, 0, 0, 0, 1, 0, 0, 0, 0], "Al-Anon"), # Family + Alcohol (loved one) -> Al-Anon
        ]

        # Generate 100 copies of each archetype with slight noise to help predict_proba
        for feat, label in archetypes:
            for _ in range(100):
                x_data.append(feat)
                y_data.append(label)

        return np.array(x_data), np.array(y_data)

    def predict_probabilities(self, response_features: Dict[str, int]) -> Dict[str, float]:
        # Ensure all features exist, default to 0
        vec = []
        for name in self.config.feature_names:
            vec.append(int(response_features.get(name, 0)))
        
        feature_vector = np.array([vec])
        probabilities = self.classifier.predict_proba(feature_vector)[0]
        class_labels = self.classifier.classes_

        # Create results dictionary
        results = {pid: 0.0 for pid in self.config.program_ids}
        for label, prob in zip(class_labels, probabilities):
            results[str(label)] = round(float(prob) * 100, 2)
        
        return results