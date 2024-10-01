import os
from flask import Flask

app = Flask(__name__)

@app.route("/")
def hello_world():
    return "Jai Shree Ram."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Use the PORT environment variable Render provides
    app.run(host="0.0.0.0", port=port)  # Host should be "0.0.0.0" to allow external access
