import cv2
import mediapipe as mp
import pickle
import numpy as np
from utils import extract_landmarks

model = pickle.load(open("../models/sign_model.pkl", "rb"))

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=1)
mp_draw = mp.solutions.drawing_utils

cap = cv2.VideoCapture(0)

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

            cv2.putText(frame, f"Letter: {letter}",
                        (40, 100), cv2.FONT_HERSHEY_SIMPLEX,
                        2, (0, 255, 0), 3)

    cv2.imshow("Sign Language Recognition", frame)
    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
