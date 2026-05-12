import sys
import os
import json

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ..model import DedupModel

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_path = os.path.join(base_dir, "data", "labeled_pairs.json")
    model_path = os.path.join(base_dir, "models", "dedup_model.pkl")
    
    if not os.path.exists(data_path):
        print(f"Error: Labeled data not found at {data_path}")
        return
        
    print(f"Loading labeled data from {data_path}...")
    with open(data_path, "r", encoding="utf-8") as f:
        labeled_pairs = json.load(f)
        
    # Load feedback if exists
    feedback_path = os.path.join(base_dir, "data", "feedback.jsonl")
    if os.path.exists(feedback_path):
        print(f"Loading additional feedback from {feedback_path}...")
        with open(feedback_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    labeled_pairs.append(json.loads(line))
        
    print(f"Training model with {len(labeled_pairs)} total samples...")
    model = DedupModel(model_path=model_path)
    result = model.train(labeled_pairs)
    
    if result["status"] == "success":
        print(f"Successfully trained and saved model to {model_path}")
    else:
        print("Training failed.")

if __name__ == "__main__":
    main()
