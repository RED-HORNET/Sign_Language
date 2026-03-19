import cv2
import mediapipe as mp
import numpy as np
import os
from utils import extract_landmarks

letter = input("Enter letter (A-Z): ").upper()
LABEL = ord(letter) - 65

# Create image folder
image_folder = f"../dataset_images/{letter}"
os.makedirs("../data", exist_ok=True)
os.makedirs("../data", exist_ok=True)

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
                # Save landmark data
                X.append(features)
                y.append(LABEL)

                # Save image
                img_path = os.path.join(image_folder, f"{img_count}.jpg")
                cv2.imwrite(img_path, frame)
                img_count += 1

                print("Sample saved")

    cv2.imshow("Collect Data", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()

# Append old data if exists
if os.path.exists("../data/X.npy"):
    X_old = np.load("../data/X.npy")
    y_old = np.load("../data/y.npy")
    X = np.vstack((X_old, X))
    y = np.hstack((y_old, y))

np.save("../data/X.npy", np.array(X))
np.save("../data/y.npy", np.array(y))

print("Data saved successfully")
