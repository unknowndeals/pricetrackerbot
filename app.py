import os
from flask import Flask

app = Flask(__name__)

@app.route("/")
def hello_world():
    return "Jai Shree Ram."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Get the PORT from environment variable or use 5000 as default
    app.run(host="0.0.0.0", port=port)  # Host 0.0.0.0 makes it accessible from outside
