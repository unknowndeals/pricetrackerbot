import os
from flask import Flask

app = Flask(__name__)

@app.route("/")
def hello_world():
    return "Jai Shree Ram."

if __name__ == "__main__":
    # Get the PORT from the environment, default to 8000 if not set
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)  # Host should be "0.0.0.0"

