import os
import joblib
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from .feature_engineering import build_feature_vector

class DedupModel:
    def __init__(self, model_path: str = None):
        if model_path is None:
            # Default path relative to this file
            base_dir = os.path.dirname(os.path.abspath(__file__))
            model_path = os.path.join(base_dir, "models", "dedup_model.pkl")
            
        self.model_path = model_path
        self.model = None
        self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
            except Exception as e:
                print(f"Error loading model from {self.model_path}: {e}")
                self.model = None

    def train(self, labeled_pairs: list) -> dict:
        """
        Trains the RandomForest model.
        labeled_pairs: [{"row_a": {}, "row_b": {}, "is_duplicate": 0 or 1}, ...]
        """
        X = []
        y = []
        
        for pair in labeled_pairs:
            features = build_feature_vector(pair["row_a"], pair["row_b"])
            # Ensure consistent feature order
            X.append(list(features.values()))
            y.append(pair["is_duplicate"])
            
        X = np.array(X)
        y = np.array(y)
        
        # RandomForest Classifier
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=5,
            random_state=42
        )
        
        self.model.fit(X, y)
        
        # Save after training
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(self.model, self.model_path)
        
        return {"status": "success", "samples": len(labeled_pairs)}

    def predict_proba(self, row_a: dict, row_b: dict) -> float:
        """
        Returns the probability of being a duplicate (0.0 to 1.0).
        """
        if self.model is None:
            return 0.0
            
        features = build_feature_vector(row_a, row_b)
        X = np.array([list(features.values())])
        
        # RandomForest predict_proba returns [prob_0, prob_1]
        probs = self.model.predict_proba(X)
        return float(probs[0][1])

    def is_duplicate(self, row_a: dict, row_b: dict, threshold: float = 0.7) -> bool:
        if self.model is None:
            return False
        return self.predict_proba(row_a, row_b) >= threshold
