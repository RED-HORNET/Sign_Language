import numpy as np
import pickle
import os
from sklearn.ensemble import RandomForestClassifier

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(BASE_DIR, "data")
MODEL_DIR = os.path.join(BASE_DIR, "models")

X = np.load(os.path.join(DATA_DIR, "X_words.npy"))
y = np.load(os.path.join(DATA_DIR, "y_words.npy"))

model = RandomForestClassifier(n_estimators=300, random_state=42)
model.fit(X, y)

os.makedirs(MODEL_DIR, exist_ok=True)

with open(os.path.join(MODEL_DIR, "word_model.pkl"), "wb") as f:
    pickle.dump(model, f)

print("Word model trained and saved successfully.")
