import json
import os
import pandas as pd
from ..dedup_engine import is_duplicate, preprocess

def test_accuracy_on_gold_dataset():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    gold_path = os.path.join(base_dir, "fixtures", "gold_dataset.json")
    
    with open(gold_path, "r", encoding="utf-8") as f:
        gold_data = json.load(f)
        
    tp = 0 # True Positives
    fp = 0 # False Positives
    tn = 0 # True Negatives
    fn = 0 # False Negatives
    
    for item in gold_data:
        row_a = item["row_a"]
        row_b = item["row_b"]
        expected = item["is_duplicate"]
        
        # We need a dataframe context for preprocess
        df = pd.DataFrame([row_a, row_b])
        df = preprocess(df)
        
        actual, reason, score = is_duplicate(df, 0, 1)
        actual_int = 1 if actual else 0
        
        if expected == 1 and actual_int == 1:
            tp += 1
        elif expected == 0 and actual_int == 1:
            fp += 1
            print(f"FP: Expected {expected}, Actual {actual_int}. Reason: {reason}. Pair: {row_a['name']} vs {row_b['name']}")
        elif expected == 0 and actual_int == 0:
            tn += 1
        elif expected == 1 and actual_int == 0:
            fn += 1
            print(f"FN: Expected {expected}, Actual {actual_int}. Pair: {row_a['name']} vs {row_b['name']}")
            
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    print(f"\n--- Accuracy Report ---")
    print(f"Precision: {precision:.2f}")
    print(f"Recall:    {recall:.2f}")
    print(f"F1 Score:  {f1:.2f}")
    print(f"Total:     {len(gold_data)}")
    
    # Assertions for CI
    assert precision >= 0.8, f"Precision too low: {precision}"
    assert recall >= 0.8, f"Recall too low: {recall}"

if __name__ == "__main__":
    test_accuracy_on_gold_dataset()
