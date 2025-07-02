import os
import pandas as pd
import requests
from flask import Blueprint, render_template, redirect, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import User
from functools import wraps
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env

# Blueprint setup
dashboard_bp = Blueprint('dashboard_bp', __name__, template_folder='templates', static_folder='static')

def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user or not user.is_admin:
            return redirect(url_for('user_bp.get_open_positions'))  # or return a 403
        return fn(*args, **kwargs)
    return wrapper

@dashboard_bp.route('/dashboard')
@admin_required
def dashboard():
    vix_data = get_vix_data()
    dxy_data = get_dxy_data()
    usdeur_data = get_usdeur_data()
    return render_template('dashboard.html', vix_data=vix_data, dxy_data=dxy_data, usdeur_data=usdeur_data)

def get_vix_data():
    """Get VIX 5-minute interval data from Twelve Data"""
    api_key = os.getenv("TWELVE_DATA_API_KEY")
    url = f"https://api.twelvedata.com/time_series?symbol=VIX&interval=5min&outputsize=36&apikey={api_key}"
    response = requests.get(url)
    data = response.json()

    if "values" not in data:
        return []

    vix_data = []
    for item in reversed(data["values"]):  # Oldest to newest
        vix_data.append({
            "Datetime": pd.to_datetime(item["datetime"]),
            "Open": float(item["open"]),
            "High": float(item["high"]),
            "Low": float(item["low"]),
            "Close": float(item["close"]),
        })

    return vix_data

def get_dxy_data():
    """Get DXY data from Finnhub using 5-minute candles"""
    api_key = os.getenv("FINNHUB_API_KEY")
    url = f"https://finnhub.io/api/v1/forex/candle?symbol=OANDA:DXY_USD&resolution=5&count=36&token={api_key}"
    response = requests.get(url)
    data = response.json()

    if "t" not in data or not data["t"]:
        return []

    dxy_data = []
    for i in range(len(data["t"])):
        dxy_data.append({
            "Datetime": pd.to_datetime(data["t"][i], unit='s'),
            "Open": data["o"][i],
            "High": data["h"][i],
            "Low": data["l"][i],
            "Close": data["c"][i],
        })

    return dxy_data

def get_usdeur_data():
    """Get EUR/USD 5-minute interval data from Twelve Data"""
    api_key = os.getenv("TWELVE_DATA_API_KEY")
    url = f"https://api.twelvedata.com/time_series?symbol=EUR/USD&interval=5min&outputsize=36&apikey={api_key}"
    response = requests.get(url)
    data = response.json()

    if "values" not in data:
        return []

    fx_data = []
    for item in reversed(data["values"]):  # Oldest to newest
        fx_data.append({
            "Datetime": pd.to_datetime(item["datetime"]),
            "Open": float(item["open"]),
            "High": float(item["high"]),
            "Low": float(item["low"]),
            "Close": float(item["close"]),
        })

    return fx_data
