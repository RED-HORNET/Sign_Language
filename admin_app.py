from flask import Flask, render_template, Response, jsonify, request, session, redirect, url_for, make_response
import jwt
import datetime
import bcrypt
import mysql.connector
import cv2
import os
import shutil
import mediapipe as mp
import numpy as np
import pickle
import time
import logging
from version2.utils import extract_landmarks
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier

app = Flask(__name__)
app.secret_key = "super_secret_login_key"

# ─── JWT ────────────────────────────────────────────────────────────────────────
JWT_SECRET    = "jwt_super_secret_key_change_in_production"
JWT_ALGORITHM = "HS256"
JWT_EXP_HOURS = 2

# ─── Audit Log (file-based) ─────────────────────────────────────────────────────
LOG_DIR  = "logs"
LOG_FILE = os.path.join(LOG_DIR, "audit.log")

os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
audit_logger = logging.getLogger("audit")

def log_action(username: str, action: str, ip: str, detail: str = ""):
    """Append one line to logs/audit.log."""
    line = f"{action:<10} | user={username:<15} | ip={ip}"
    if detail:
        line += f" | {detail}"
    audit_logger.info(line)

# ─── Rate Limiter (in-memory) ───────────────────────────────────────────────────
RATE_LIMIT_MAX     = 5           # max failed attempts
RATE_LIMIT_WINDOW  = 15 * 60    # 15-minute lockout window (seconds)
_failed_attempts: dict = {}      # { ip: {"count": int, "first_fail": float} }

def is_rate_limited(ip: str) -> tuple[bool, int]:
    """Return (is_blocked, seconds_remaining). Purges expired entries."""
    now = time.time()
    entry = _failed_attempts.get(ip)
    if entry is None:
        return False, 0
    elapsed = now - entry["first_fail"]
    if elapsed > RATE_LIMIT_WINDOW:
        del _failed_attempts[ip]
        return False, 0
    if entry["count"] >= RATE_LIMIT_MAX:
        remaining = int(RATE_LIMIT_WINDOW - elapsed)
        return True, remaining
    return False, 0

def record_failure(ip: str):
    now = time.time()
    if ip not in _failed_attempts:
        _failed_attempts[ip] = {"count": 1, "first_fail": now}
    else:
        _failed_attempts[ip]["count"] += 1

def clear_failures(ip: str):
    _failed_attempts.pop(ip, None)

# ─── DB ─────────────────────────────────────────────────────────────────────────
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Monster",
        database="sign_language_db"
    )

# ─── Auth Guard ─────────────────────────────────────────────────────────────────
@app.before_request
def require_login():
    allowed_routes = ['login', 'static']
    if request.endpoint in allowed_routes:
        return

    token = request.cookies.get('jwt_token')
    if not token:
        return redirect(url_for('login'))

    try:
        jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        resp = make_response(redirect(url_for('login')))
        resp.delete_cookie('jwt_token')
        return resp
    except jwt.InvalidTokenError:
        resp = make_response(redirect(url_for('login')))
        resp.delete_cookie('jwt_token')
        return resp

# ─── Login / Logout ─────────────────────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    message = ""
    lockout_seconds = 0

    if request.method == 'POST':
        ip = request.remote_addr
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        # Check rate limit
        blocked, lockout_seconds = is_rate_limited(ip)
        if blocked:
            mins = lockout_seconds // 60
            secs = lockout_seconds % 60
            message = f"Too many failed attempts. Try again in {mins}m {secs}s."
            return render_template("login.html", message=message, lockout=True, lockout_seconds=lockout_seconds)

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM admin_users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        db.close()

        valid = False
        if user:
            stored = user["password_hash"]
            # Support both bcrypt hashes and plain text (fallback during migration)
            if stored.startswith("$2b$") or stored.startswith("$2a$"):
                try:
                    valid = bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
                except Exception:
                    valid = False
            else:
                valid = (password == stored)

        if valid:
            clear_failures(ip)
            log_action(user["username"], "LOGIN", ip)

            payload = {
                'username': user['username'],
                'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=JWT_EXP_HOURS)
            }
            token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
            resp = make_response(redirect(url_for('admin')))
            resp.set_cookie('jwt_token', token, httponly=True, samesite='Lax', max_age=JWT_EXP_HOURS * 3600)
            return resp
        else:
            record_failure(ip)
            remaining = RATE_LIMIT_MAX - _failed_attempts.get(ip, {}).get("count", 0)
            if remaining > 0:
                message = f"Invalid username or password. {remaining} attempt(s) remaining."
            else:
                message = f"Account locked for {RATE_LIMIT_WINDOW // 60} minutes due to too many failed attempts."

    return render_template("login.html", message=message, lockout=False, lockout_seconds=0)


@app.route('/logout')
def logout():
    token = request.cookies.get('jwt_token')
    username = "unknown"
    if token:
        try:
            data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            username = data.get("username", "unknown")
        except Exception:
            pass
    log_action(username, "LOGOUT", request.remote_addr)
    session.clear()
    resp = make_response(redirect(url_for('login')))
    resp.delete_cookie('jwt_token')
    return resp

# ─── Helper: get current user from JWT ──────────────────────────────────────────
def current_user() -> str:
    token = request.cookies.get('jwt_token')
    if not token:
        return "unknown"
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return data.get("username", "unknown")
    except Exception:
        return "unknown"

# ─── Camera State ───────────────────────────────────────────────────────────────
camera = None
running = False
hand_status = False
live_prediction_state = {"word": "-", "confidence": 0.0, "time": 0.0, "hand_detected": False}

# ─── Model ──────────────────────────────────────────────────────────────────────
try:
    model = pickle.load(open("models/word_model.pkl", "rb"))
except Exception:
    model = None

try:
    labels    = np.load("data/word_labels.npy", allow_pickle=True).item()
    label_map = {v: k for k, v in labels.items()}
except Exception:
    labels    = {}
    label_map = {}

# ─── MediaPipe ──────────────────────────────────────────────────────────────────
mp_hands = mp.solutions.hands
hands    = mp_hands.Hands(max_num_hands=2)
mp_draw  = mp.solutions.drawing_utils

# ─── Admin Mode ─────────────────────────────────────────────────────────────────
app_mode          = 'predict'
collect_target_word = ''
collect_trigger   = False


def save_collection_sample(features, word, frame):
    DATA_DIR  = "data"
    IMAGE_DIR = "dataset_images"
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(IMAGE_DIR, exist_ok=True)

    word_upper   = word.upper()
    image_folder = os.path.join(IMAGE_DIR, word_upper)
    os.makedirs(image_folder, exist_ok=True)

    label_file = os.path.join(DATA_DIR, "word_labels.npy")
    if os.path.exists(label_file):
        labels_dict = np.load(label_file, allow_pickle=True).item()
    else:
        labels_dict = {}

    if word_upper not in labels_dict:
        labels_dict[word_upper] = len(labels_dict)
    LABEL = labels_dict[word_upper]
    np.save(label_file, labels_dict)

    X_path = os.path.join(DATA_DIR, "X_words.npy")
    y_path = os.path.join(DATA_DIR, "y_words.npy")

    if os.path.exists(X_path):
        X = list(np.load(X_path))
        y = list(np.load(y_path))
    else:
        X, y = [], []

    X.append(features)
    y.append(LABEL)

    np.save(X_path, np.array(X))
    np.save(y_path, np.array(y))

    img_count = len(os.listdir(image_folder))
    img_path  = os.path.join(image_folder, f"{img_count}.jpg")
    cv2.imwrite(img_path, frame)


def generate_frames():
    global camera, running, hand_status
    global app_mode, collect_target_word, collect_trigger
    global live_prediction_state

    if camera is None:
        camera = cv2.VideoCapture(0)

    running = True

    while running:
        success, frame = camera.read()
        if not success:
            break

        frame        = cv2.flip(frame, 1)
        rgb          = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result       = hands.process(rgb)
        hand_detected = False
        live_prediction_state["hand_detected"] = False

        if result.multi_hand_landmarks:
            hand_detected = True
            live_prediction_state["hand_detected"] = True

            for hand_landmarks in result.multi_hand_landmarks:
                mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                features = extract_landmarks(hand_landmarks)

                if app_mode == 'predict':
                    if model is not None:
                        try:
                            start_time   = time.time()
                            prediction   = model.predict([features])[0]
                            word         = label_map.get(prediction, "Unknown")

                            if hasattr(model, "predict_proba"):
                                probabilities = model.predict_proba([features])[0]
                                confidence    = np.max(probabilities) * 100
                            else:
                                confidence = 100.0

                            inference_time = time.time() - start_time

                            live_prediction_state["word"]       = word
                            live_prediction_state["confidence"] = round(confidence, 1)
                            live_prediction_state["time"]       = round(inference_time, 3)

                            cv2.putText(frame, f"{word} {confidence:.1f}%", (20, 80),
                                        cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)
                        except Exception:
                            cv2.putText(frame, "Model error", (20, 80),
                                        cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)
                            live_prediction_state.update({"word": "Error", "confidence": 0.0, "time": 0.0})
                    else:
                        cv2.putText(frame, "No model loaded", (20, 80),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)

                elif app_mode == 'collect':
                    cv2.putText(frame, f"Collecting: {collect_target_word}", (20, 80),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 165, 255), 3)
                    if collect_trigger:
                        save_collection_sample(features, collect_target_word, frame.copy())
                        collect_trigger = False
                        cv2.putText(frame, "SAVED!", (20, 150), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 4)
        else:
            if app_mode == 'predict':
                live_prediction_state.update({"word": "-", "confidence": 0.0, "time": 0.0})

        hand_status = hand_detected
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    if camera is not None:
        camera.release()


# ─── Routes ─────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return redirect(url_for('admin'))

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/video')
def video():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/hand_status')
def hand_status_route():
    return jsonify({"hand": hand_status})

@app.route('/api/live_stats')
def live_stats():
    return jsonify(live_prediction_state)

@app.route('/api/dataset_stats')
def dataset_stats():
    IMAGE_DIR = "dataset_images"
    total_words, total_samples, images_per_word = 0, 0, {}

    if os.path.exists(IMAGE_DIR):
        folders = os.listdir(IMAGE_DIR)
        total_words = len(folders)
        for folder in folders:
            folder_path = os.path.join(IMAGE_DIR, folder)
            if os.path.isdir(folder_path):
                num = len(os.listdir(folder_path))
                images_per_word[folder] = num
                total_samples += num

    return jsonify({"total_words": total_words, "total_samples": total_samples, "images_per_word": images_per_word})

@app.route('/api/get_words')
def get_words():
    IMAGE_DIR = "dataset_images"
    words = []
    if os.path.exists(IMAGE_DIR):
        for folder in os.listdir(IMAGE_DIR):
            folder_path = os.path.join(IMAGE_DIR, folder)
            if os.path.isdir(folder_path):
                words.append({"word": folder, "count": len(os.listdir(folder_path))})
    return jsonify({"words": words})

@app.route('/api/delete_word', methods=['POST'])
def delete_word():
    data          = request.json
    word_to_delete = data.get('word', '').upper()
    DATA_DIR      = "data"
    IMAGE_DIR     = "dataset_images"

    folder_path = os.path.join(IMAGE_DIR, word_to_delete)
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)

    label_file = os.path.join(DATA_DIR, "word_labels.npy")
    if os.path.exists(label_file):
        labels_dict = np.load(label_file, allow_pickle=True).item()
        if word_to_delete in labels_dict:
            label_id = labels_dict.pop(word_to_delete)
            np.save(label_file, labels_dict)

            X_path = os.path.join(DATA_DIR, "X_words.npy")
            y_path = os.path.join(DATA_DIR, "y_words.npy")
            if os.path.exists(X_path) and os.path.exists(y_path):
                try:
                    X, y   = np.load(X_path), np.load(y_path)
                    mask   = y != label_id
                    np.save(X_path, X[mask])
                    np.save(y_path, y[mask])
                except Exception as e:
                    return jsonify({"status": "error", "message": f"Failed to update dataset: {e}"})

    log_action(current_user(), "DELETE_WORD", request.remote_addr, f"word={word_to_delete}")
    return jsonify({"status": "success", "message": f"Deleted {word_to_delete} from dataset."})

@app.route('/stop_camera')
def stop_camera():
    global running, camera
    running = False
    if camera is not None:
        camera.release()
        camera = None
    return jsonify({"status": "Camera stopped"})

@app.route('/api/update_model', methods=['POST'])
def update_model():
    global model, labels, label_map
    try:
        model     = pickle.load(open("models/word_model.pkl", "rb"))
        labels    = np.load("data/word_labels.npy", allow_pickle=True).item()
        label_map = {v: k for k, v in labels.items()}
        return jsonify({"status": "success", "message": "Model updated successfully!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/start_collection', methods=['POST'])
def start_collection():
    global app_mode, collect_target_word
    data = request.json
    collect_target_word = data.get('word', '').upper()
    app_mode = 'collect'
    return jsonify({"status": "success"})

@app.route('/api/capture_sample', methods=['POST'])
def capture_sample():
    global collect_trigger
    collect_trigger = True
    return jsonify({"status": "success"})

@app.route('/api/stop_collection', methods=['POST'])
def stop_collection():
    global app_mode, live_prediction_state
    app_mode = 'predict'
    live_prediction_state = {"word": "-", "confidence": 0.0, "time": 0.0, "hand_detected": False}
    return jsonify({"status": "success"})

@app.route('/api/train_model', methods=['POST'])
def train_model():
    try:
        global label_map
        DATA_DIR  = "data"
        MODEL_DIR = "models"
        X = np.load(os.path.join(DATA_DIR, "X_words.npy"))
        y = np.load(os.path.join(DATA_DIR, "y_words.npy"))

        if len(X) < 10:
            return jsonify({"status": "error", "message": "Not enough data to train (minimum 10 samples required)."})

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        clf = RandomForestClassifier(n_estimators=300, random_state=42)
        clf.fit(X_train, y_train)

        y_pred = clf.predict(X_test)

        stats = {
            "accuracy":  round(accuracy_score(y_test, y_pred) * 100, 1),
            "precision": round(precision_score(y_test, y_pred, average='weighted', zero_division=0) * 100, 1),
            "recall":    round(recall_score(y_test, y_pred, average='weighted', zero_division=0) * 100, 1),
            "f1":        round(f1_score(y_test, y_pred, average='weighted', zero_division=0) * 100, 1),
        }

        cm        = confusion_matrix(y_test, y_pred, labels=clf.classes_)
        cm_labels = [label_map.get(c, f"C{c}") for c in clf.classes_]

        os.makedirs(MODEL_DIR, exist_ok=True)
        with open(os.path.join(MODEL_DIR, "word_model.pkl"), "wb") as f:
            pickle.dump(clf, f)

        log_action(current_user(), "TRAIN", request.remote_addr, f"acc={stats['accuracy']}%")
        return jsonify({
            "status": "success",
            "message": "Word model trained and saved successfully.",
            "stats": stats,
            "confusion_matrix": cm.tolist(),
            "cm_labels": cm_labels
        })
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)})


# ─── Multi-Model Test (admin only) ──────────────────────────────────────────────
@app.route('/api/test_models', methods=['POST'])
def test_models():
    """Train & evaluate RF, SVM, KNN side-by-side. Does NOT save any model."""
    try:
        DATA_DIR = "data"
        X = np.load(os.path.join(DATA_DIR, "X_words.npy"))
        y = np.load(os.path.join(DATA_DIR, "y_words.npy"))

        if len(X) < 10:
            return jsonify({"status": "error", "message": "Not enough data (minimum 10 samples)."})

        body      = request.get_json(silent=True) or {}
        requested = body.get("models", ["rf", "svm", "knn"])

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        candidates = {}
        if "rf" in requested:
            candidates["Random Forest"] = RandomForestClassifier(n_estimators=100, random_state=42)
        if "svm" in requested:
            candidates["SVM"] = SVC(kernel='rbf', probability=True, random_state=42)
        if "knn" in requested:
            candidates["KNN"] = KNeighborsClassifier(n_neighbors=5)

        results = []
        for name, clf in candidates.items():
            t0 = time.time()
            clf.fit(X_train, y_train)
            train_time = round(time.time() - t0, 2)

            y_pred = clf.predict(X_test)
            results.append({
                "model":     name,
                "accuracy":  round(accuracy_score(y_test, y_pred) * 100, 1),
                "precision": round(precision_score(y_test, y_pred, average='weighted', zero_division=0) * 100, 1),
                "recall":    round(recall_score(y_test, y_pred, average='weighted', zero_division=0) * 100, 1),
                "f1":        round(f1_score(y_test, y_pred, average='weighted', zero_division=0) * 100, 1),
                "train_time": train_time
            })

        log_action(current_user(), "TEST_MODELS", request.remote_addr, f"models={requested}")
        return jsonify({"status": "success", "results": results})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)})


# ─── Data Augmentation ──────────────────────────────────────────────────────────
@app.route('/api/augment_data', methods=['POST'])
def augment_data():
    """
    Apply flips and rotations to images in dataset_images/ and store the
    augmented copies in dataset_images_augmented/ (separate folder, never mixed).
    """
    IMAGE_DIR = "dataset_images"
    AUG_DIR   = "dataset_images_augmented"

    if not os.path.exists(IMAGE_DIR):
        return jsonify({"status": "error", "message": "No dataset images found."})

    os.makedirs(AUG_DIR, exist_ok=True)

    AUGMENTATIONS = [
        ("flip_h",  lambda img: cv2.flip(img, 1)),
        ("rot_10",  lambda img: _rotate(img,  10)),
        ("rot_neg10", lambda img: _rotate(img, -10)),
        ("rot_20",  lambda img: _rotate(img,  20)),
        ("rot_neg20", lambda img: _rotate(img, -20)),
    ]

    total_saved = 0

    for word_folder in os.listdir(IMAGE_DIR):
        src_folder = os.path.join(IMAGE_DIR, word_folder)
        if not os.path.isdir(src_folder):
            continue

        dst_folder = os.path.join(AUG_DIR, word_folder)
        os.makedirs(dst_folder, exist_ok=True)

        for img_file in os.listdir(src_folder):
            if not img_file.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
            img_path = os.path.join(src_folder, img_file)
            img      = cv2.imread(img_path)
            if img is None:
                continue

            stem = os.path.splitext(img_file)[0]
            for aug_name, aug_fn in AUGMENTATIONS:
                aug_img   = aug_fn(img)
                save_path = os.path.join(dst_folder, f"{stem}_{aug_name}.jpg")
                cv2.imwrite(save_path, aug_img)
                total_saved += 1

    log_action(current_user(), "AUGMENT", request.remote_addr, f"generated={total_saved}")
    return jsonify({
        "status": "success",
        "message": f"Augmentation complete. {total_saved} images saved to '{AUG_DIR}/'.",
        "total_saved": total_saved
    })


def _rotate(img, angle: float):
    """Rotate image by angle degrees around centre, keeping same size."""
    h, w = img.shape[:2]
    M    = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REFLECT)


# ─── Entry Point ────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True, port=5001)
