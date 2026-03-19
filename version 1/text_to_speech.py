import pyttsx3

# Initialize engine
engine = pyttsx3.init()

# Optional: Adjust voice speed
engine.setProperty('rate', 150)

# Optional: Adjust volume (0.0 to 1.0)
engine.setProperty('volume', 1.0)

# Read text from file
with open("output.txt", "r", encoding="utf-8") as f:
    text = f.read()

if text.strip() == "":
    print("File is empty.")
else:
    print("Speaking...")
    engine.say(text)
    engine.runAndWait()
