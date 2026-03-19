How to Run the Project (Simple Guide)
1. Clone the repository

Open terminal / cmd

git clone https://github.com/your-username/sign_language_project.git

Go inside project

cd sign_language_project
2. Install required libraries

Make sure Python 3.10 is installed.

Install dependencies:

pip install opencv-python mediapipe==0.10.9 numpy scikit-learn pyttsx3 flask

or

pip install -r requirements.txt
3. Check required files

Make sure these folders exist:

data/
models/
version2/
templates/
static/

Make sure these files exist:

models/word_model.pkl
data/word_labels.npy
output_words.txt
app.py

If model not present, run:

python version2/train_word_model.py
4. Run the project

Run Flask server:

python app.py

Open browser:

http://127.0.0.1:5000
5. How to use

Click Start Detection

Show hand sign in camera

Click Show Text

Click Speak

Output saved in:

output_words.txt
