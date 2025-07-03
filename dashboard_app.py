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
    from datetime import datetime, timedelta
    import json
    
    # Generate sample time series data
    base_time = datetime.now()
    
    mock_vix_data = []
    mock_dxy_data = []
    mock_usdeur_data = []
    
    for i in range(10):
        time_point = (base_time - timedelta(minutes=i*5)).strftime("%Y-%m-%d %H:%M:%S")
        
        mock_vix_data.append({
            "Datetime": time_point,
            "Open": 20.5 + i * 0.1,
            "High": 21.0 + i * 0.1,
            "Low": 20.0 + i * 0.1,
            "Close": 20.8 + i * 0.1
        })
        
        mock_dxy_data.append({
            "Datetime": time_point,
            "Open": 103.5 + i * 0.05,
            "High": 104.0 + i * 0.05,
            "Low": 103.0 + i * 0.05,
            "Close": 103.8 + i * 0.05
        })
        
        mock_usdeur_data.append({
            "Datetime": time_point,
            "Open": 1.0850 + i * 0.001,
            "High": 1.0900 + i * 0.001,
            "Low": 1.0800 + i * 0.001,
            "Close": 1.0875 + i * 0.001
        })
    
    # Reverse to get chronological order
    mock_vix_data.reverse()
    mock_dxy_data.reverse()
    mock_usdeur_data.reverse()
    
    return render_template("dashboard.html", 
                         vix_data=mock_vix_data, 
                         dxy_data=mock_dxy_data, 
                         usdeur_data=mock_usdeur_data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)
