from flask import Flask, render_template
from dashboard.routes import dashboard_bp

from dotenv import load_dotenv
import os

load_dotenv()  # Loads variables from .env

# Example usage:
secret_key = os.getenv("FLASK_SECRET")


app = Flask(__name__)
app.register_blueprint(dashboard_bp, url_prefix="/")

@app.route("/")
def home():
    return render_template("dashboard.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)
