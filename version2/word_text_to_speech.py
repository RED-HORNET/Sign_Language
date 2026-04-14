import pyttsx3
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_FILE = os.path.join(BASE_DIR, "output_words.txt")

engine = pyttsx3.init()
engine.setProperty('rate', 200)
engine.setProperty('volume', 1.0)

import sys

if len(sys.argv) > 1:
    text = " ".join(sys.argv[1:])
else:
    if not os.path.exists(OUTPUT_FILE):
        print("No output file found.")
        text = ""
    else:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            text = f.read()

if text.strip() == "":
    print("File is empty.")
else:
    print("Speaking...")
    engine.say(text)
    engine.runAndWait()
