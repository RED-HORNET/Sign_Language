import numpy as np
import pickle
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import os


X = np.load("../data/X.npy")
y = np.load("../data/y.npy")

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = RandomForestClassifier(n_estimators=200,random_state=42)

model.fit(X_train, y_train)

y_pred = model.predict(X_test)
print("Accuracy:", accuracy_score(y_test, y_pred))

os.makedirs("../models", exist_ok=True)

with open("../models/sign_model.pkl", "wb") as f:
    pickle.dump(model, f)

print("Model saved successfully")
