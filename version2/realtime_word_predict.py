import cv2
import mediapipe as mp
import pickle
import numpy as np
import os
from utils import extract_landmarks

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(BASE_DIR, "data")
MODEL_DIR = os.path.join(BASE_DIR, "models")
OUTPUT_FILE = os.path.join(BASE_DIR, "output_words.txt")

# Load model
model = pickle.load(open(os.path.join(MODEL_DIR, "word_model.pkl"), "rb"))

# Load labels
labels = np.load(os.path.join(DATA_DIR, "word_labels.npy"), allow_pickle=True).item()
label_map = {v: k for k, v in labels.items()}

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=2)
mp_draw = mp.solutions.drawing_utils

cap = cv2.VideoCapture(0)

sentence = ""

while True:
    ret, frame = cap.read()
    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    result = hands.process(rgb)

    if result.multi_hand_landmarks:
        for hand_landmarks in result.multi_hand_landmarks:
            mp_draw.draw_landmarks(frame,
                                   hand_landmarks,
                                   mp_hands.HAND_CONNECTIONS)

            features = extract_landmarks(hand_landmarks)
            prediction = model.predict([features])[0]
            word = label_map[prediction]

            cv2.putText(frame, f"Word: {word}",
                        (30, 100),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        2,
                        (0, 255, 0),
                        3)

            sentence = word

    cv2.putText(frame, f"Text: {sentence}",
                (30, 160),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (255, 0, 0),
                2)

    cv2.imshow("Word to File", frame)
    key = cv2.waitKey(1) & 0xFF

    # ENTER → Save to file
    if key == 13 or key == 10:
        with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
            f.write(sentence + "\n")
        print("Saved to output_words.txt")

    # ESC → Exit
    if key == 27:
        break

cap.release()
cv2.destroyAllWindows()
