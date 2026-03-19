import cv2
import mediapipe as mp
import numpy as np
import os
from utils import extract_landmarks

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Global folders
DATA_DIR = os.path.join(BASE_DIR, "data")
IMAGE_DIR = os.path.join(BASE_DIR, "dataset_images")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)

word = input("Enter word label (e.g., HELLO): ").upper()

image_folder = os.path.join(IMAGE_DIR, word)
os.makedirs(image_folder, exist_ok=True)

# Label mapping file
label_file = os.path.join(DATA_DIR, "word_labels.npy")

if os.path.exists(label_file):
    labels = np.load(label_file, allow_pickle=True).item()
else:
    labels = {}

if word not in labels:
    labels[word] = len(labels)

LABEL = labels[word]
np.save(label_file, labels)

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=1)

cap = cv2.VideoCapture(0)

X, y = [], []
img_count = len(os.listdir(image_folder))

while True:
    ret, frame = cap.read()
    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    result = hands.process(rgb)

    if result.multi_hand_landmarks:
        for hand_landmarks in result.multi_hand_landmarks:
            features = extract_landmarks(hand_landmarks)

            cv2.putText(frame, "Press S to Save",
                        (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1, (0, 255, 0), 2)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('s'):
                X.append(features)
                y.append(LABEL)

                img_path = os.path.join(image_folder, f"{img_count}.jpg")
                cv2.imwrite(img_path, frame)
                img_count += 1

                print("Sample saved")

    cv2.imshow("Collect Word Data", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()

X_path = os.path.join(DATA_DIR, "X_words.npy")
y_path = os.path.join(DATA_DIR, "y_words.npy")

if os.path.exists(X_path):
    X_old = np.load(X_path)
    y_old = np.load(y_path)
    X = np.vstack((X_old, X))
    y = np.hstack((y_old, y))

np.save(X_path, np.array(X))
np.save(y_path, np.array(y))

print("Word data saved successfully.")
