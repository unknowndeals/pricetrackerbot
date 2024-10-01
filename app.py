import os
from flask import Flask
from pyrogram import Client, filters

app = Flask(__name__)

@app.route("/")
def hello_world():
    return "Jai Shree Ram."

if __name__ == "__main__":
    bot.start()  # Start the bot
    app.run(host='0.0.0.0', port=os.getenv("PORT", 8080))  # Flask app runs on this port
