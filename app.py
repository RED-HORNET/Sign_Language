from flask import Flask, render_template, Response, jsonify
import cv2
import os
import mediapipe as mp
import numpy as np
import pickle
import time
from version2.utils import extract_landmarks

app = Flask(__name__)

# Camera state
camera = None
running = False
hand_status = False

# Output file
OUTPUT_FILE = "output_words.txt"

# Gesture stabilizer
last_word = ""
current_word = ""
word_start_time = 0
STABLE_TIME = 1

# Load model
model = pickle.load(open("models/word_model.pkl", "rb"))

# Load labels
labels = np.load("data/word_labels.npy", allow_pickle=True).item()
label_map = {v: k for k, v in labels.items()}

# MediaPipe
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=2)
mp_draw = mp.solutions.drawing_utils


def generate_frames():

    global camera, running, hand_status
    global last_word, current_word, word_start_time

    if camera is None:
        camera = cv2.VideoCapture(0)

    running = True

    while running:

        success, frame = camera.read()
        if not success:
            break

        frame = cv2.flip(frame, 1)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb)

        hand_detected = False

        if result.multi_hand_landmarks:

            hand_detected = True

            for hand_landmarks in result.multi_hand_landmarks:

                mp_draw.draw_landmarks(
                    frame,
                    hand_landmarks,
                    mp_hands.HAND_CONNECTIONS
                )

                features = extract_landmarks(hand_landmarks)

                prediction = model.predict([features])[0]
                word = label_map[prediction]

                cv2.putText(
                    frame,
                    f"Word: {word}",
                    (20, 80),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.5,
                    (0, 255, 0),
                    3
                )

                # Stabilization logic
                if word != current_word:

                    current_word = word
                    word_start_time = time.time()

                else:

                    if time.time() - word_start_time > STABLE_TIME and word != last_word:

                        with open(OUTPUT_FILE, "a") as f:
                            f.write(word + "\n")

                        last_word = word

        hand_status = hand_detected

        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    if camera is not None:
        camera.release()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/video')
def video():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/hand_status')
def hand_status_route():
    return jsonify({"hand": hand_status})


@app.route('/stop_camera')
def stop_camera():
    global running, camera

    running = False

    if camera is not None:
        camera.release()
        camera = None

    return jsonify({"status": "Camera stopped"})


@app.route('/get_text')
def get_text():

    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r") as f:
            text = f.read()
    else:
        text = ""

    return jsonify({"text": text})


@app.route('/clear_text')
def clear_text():

    with open(OUTPUT_FILE, "w") as f:
        f.write("")

    return jsonify({"status": "cleared"})


if __name__ == '__main__':
    app.run(debug=True)