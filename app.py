from flask import Flask, render_template, Response, jsonify, request
import cv2
import os
import mediapipe as mp
import numpy as np
import pickle
import time
import threading
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

# Model confidence (0.0 – 1.0) updated each frame
current_confidence = 0.0

# Load model
try:
    model = pickle.load(open("models/word_model.pkl", "rb"))
except:
    model = None

# Load labels
try:
    labels = np.load("data/word_labels.npy", allow_pickle=True).item()
    label_map = {v: k for k, v in labels.items()}
except:
    labels = {}
    label_map = {}

# MediaPipe
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=2)
mp_draw = mp.solutions.drawing_utils


def generate_frames():
    global camera, running, hand_status
    global last_word, current_word, word_start_time
    global current_confidence

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
                mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                features = extract_landmarks(hand_landmarks)

                if model is not None:
                    try:
                        prediction = model.predict([features])[0]
                        word = label_map.get(prediction, "Unknown")
                        cv2.putText(frame, f"Word: {word}", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)

                        # Capture confidence score
                        try:
                            proba = model.predict_proba([features])[0]
                            current_confidence = float(max(proba))
                        except Exception:
                            current_confidence = 0.0

                        # Stabilization logic
                        if word != current_word:
                            current_word = word
                            word_start_time = time.time()
                        else:
                            if time.time() - word_start_time > STABLE_TIME and word != last_word:
                                with open(OUTPUT_FILE, "a") as f:
                                    f.write(word + "\n")
                                last_word = word
                    except Exception:
                        pass

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


@app.route('/settings')
def settings():
    return render_template('settings.html')


@app.route('/video')
def video():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


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


@app.route('/speak_text', methods=['POST'])
def speak_text():
    data = request.json
    text_to_speak = data.get('text', '').strip()

    # Fall back to reading the output file if no text provided
    if not text_to_speak:
        output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output_words.txt")
        if os.path.exists(output_file):
            with open(output_file, "r", encoding="utf-8") as f:
                text_to_speak = f.read().strip()

    if not text_to_speak:
        return jsonify({"status": "empty"})

    def _speak(text):
        """Run pyttsx3 in a daemon thread — avoids blocking Flask and
           avoids Windows cmd-line Unicode encoding issues from subprocess."""
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty('rate', 175)
            engine.setProperty('volume', 1.0)
            print(f"Speaking: {text[:60]}..." if len(text) > 60 else f"Speaking: {text}")
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            print(f"TTS error: {e}")

    t = threading.Thread(target=_speak, args=(text_to_speak,), daemon=True)
    t.start()
    return jsonify({"status": "speaking"})


@app.route('/confidence')
def get_confidence():
    """Return current model prediction confidence (0–100 scale)."""
    return jsonify({"confidence": round(current_confidence * 100, 1)})


if __name__ == '__main__':
    app.run(debug=True, port=5000)