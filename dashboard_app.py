from flask import Flask, render_template
from dashboard.routes import dashboard_bp
from datetime import datetime
import json

from dotenv import load_dotenv
import os

load_dotenv()  # Loads variables from .env

# Example usage:
secret_key = os.getenv("FLASK_SECRET")

app = Flask(__name__)
app.register_blueprint(dashboard_bp, url_prefix="/dashboard")

@app.route("/")
def home():
    # Provide mock data for the dashboard template
    mock_vix_data = [
        {"Datetime": datetime.now(), "Open": 20.5, "High": 21.0, "Low": 20.0, "Close": 20.8}
    ]
    mock_dxy_data = [
        {"Datetime": datetime.now(), "Open": 103.5, "High": 104.0, "Low": 103.0, "Close": 103.8}
    ]
    mock_usdeur_data = [
        {"Datetime": datetime.now(), "Open": 1.0850, "High": 1.0900, "Low": 1.0800, "Close": 1.0875}
    ]
    
    return render_template("dashboard.html", 
                         vix_data=json.dumps(mock_vix_data, default=str), 
                         dxy_data=json.dumps(mock_dxy_data, default=str), 
                         usdeur_data=json.dumps(mock_usdeur_data, default=str))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)
