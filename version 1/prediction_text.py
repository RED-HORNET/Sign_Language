import cv2
import mediapipe as mp
import pickle
import numpy as np
import pyttsx3
from utils import extract_landmarks

# Load model
model = pickle.load(open("../models/sign_model.pkl", "rb"))

# Text-to-speech engine
engine = pyttsx3.init()

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=2)
mp_draw = mp.solutions.drawing_utils

cap = cv2.VideoCapture(0)

sentence = ""
previous_letter = ""
stable_count = 0

while True:
    ret, frame = cap.read()
    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    result = hands.process(rgb)

    if result.multi_hand_landmarks:
        for hand_landmarks in result.multi_hand_landmarks:
            mp_draw.draw_landmarks(
                frame,
                hand_landmarks,
                mp_hands.HAND_CONNECTIONS
            )

            features = extract_landmarks(hand_landmarks)
            prediction = model.predict([features])[0]
            letter = chr(prediction + 65)

            # Stability check
            if letter == previous_letter:
                stable_count += 1
            else:
                stable_count = 0

            if stable_count == 15:   # 15 frames stable
                sentence += letter
                stable_count = 0

            previous_letter = letter

            cv2.putText(frame, f"Current: {letter}",
                        (30, 80), cv2.FONT_HERSHEY_SIMPLEX,
                        1.5, (0,255,0), 3)

    # Display sentence
    cv2.putText(frame, f"Text: {sentence}",
                (30, 150), cv2.FONT_HERSHEY_SIMPLEX,
                1, (255,0,0), 2)

    cv2.imshow("Sign to Text", frame)

    key = cv2.waitKey(1) & 0xFF

    # ENTER → Save to file
    if key == 13:
        with open("output.txt", "a") as f:
            f.write(sentence + "\n")
        print("Text saved to file")
        sentence = ""

    # BACKSPACE → Remove last letter
    if key == 8:
        sentence = sentence[:-1]

    # SPACE → Add space
    if key == 32:
        sentence += " "

    # ESC → Exit
    if key == 27:
        break

cap.release()
cv2.destroyAllWindows()
