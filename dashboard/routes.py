import os
import pandas as pd
import requests
import time
import json
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import User
from functools import wraps
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env

# Blueprint setup
dashboard_bp = Blueprint('dashboard_bp', __name__, template_folder='templates', static_folder='static')

# Cache for storing latest data to avoid API rate limits
data_cache = {
    'vix': {'data': [], 'last_update': 0},
    'dxy': {'data': [], 'last_update': 0}
}

# Rate limiting configuration
CACHE_DURATION = 45  # 45 seconds cache to refresh every 45-60s
MAX_RETRIES = 3
RETRY_DELAY = 1  # Initial delay in seconds

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

def make_api_request_with_retry(url, max_retries=MAX_RETRIES):
    """Make API request with exponential backoff retry logic"""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:  # Rate limit hit
                wait_time = RETRY_DELAY * (2 ** attempt)  # Exponential backoff
                print(f"Rate limit hit, waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                time.sleep(wait_time)
            else:
                print(f"API request failed with status {response.status_code}")
                break
                
        except requests.exceptions.RequestException as e:
            print(f"Request exception on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(RETRY_DELAY * (2 ** attempt))
    
    return None

@dashboard_bp.route('/dashboard')
@admin_required
def dashboard():
    vix_data = get_vix_data()
    dxy_data = get_dxy_data()
    usdeur_data = get_usdeur_data()
    return render_template('dashboard.html', vix_data=vix_data, dxy_data=dxy_data, usdeur_data=usdeur_data)

@dashboard_bp.route('/api/live-data')
def get_live_data():
    """API endpoint for near-live data updates every 30-60s"""
    return jsonify({
        'vix': get_vix_data(),
        'dxy': get_dxy_data(),
        'eurusd': get_usdeur_data(),
        'timestamp': datetime.now().isoformat()
    })

def get_vix_data():
    """Get VIX 1-minute interval data from Twelve Data (5 points for near-live feel)"""
    current_time = time.time()
    
    # Check cache first to avoid hitting rate limits
    if (current_time - data_cache['vix']['last_update']) < CACHE_DURATION and data_cache['vix']['data']:
        print("VIX: Using cached data")
        return data_cache['vix']['data']
    
    api_key = "c6137f97a46c4ae69a47635e66d669da"  # Your Twelve Data API key
    url = f"https://api.twelvedata.com/time_series?symbol=VIX&interval=1min&outputsize=5&apikey={api_key}"
    
    print(f"VIX: Fetching fresh data from Twelve Data...")
    data = make_api_request_with_retry(url)
    
    if not data or "values" not in data:
        print("VIX: No data received, using cached data if available")
        return data_cache['vix']['data']

    vix_data = []
    for item in reversed(data["values"]):  # Oldest to newest for proper chart order
        try:
            vix_data.append({
                "Datetime": pd.to_datetime(item["datetime"]),
                "Open": float(item["open"]),
                "High": float(item["high"]),
                "Low": float(item["low"]),
                "Close": float(item["close"]),
            })
        except (ValueError, KeyError) as e:
            print(f"VIX: Error parsing data point: {e}")
            continue

    # Update cache
    if vix_data:
        data_cache['vix']['data'] = vix_data
        data_cache['vix']['last_update'] = current_time
        print(f"VIX: Cached {len(vix_data)} data points")

    return vix_data

def get_dxy_data():
    """Get DXY data from Finnhub using 1-minute candles (5 points for near-live feel)"""
    current_time = time.time()
    
    # Check cache first to avoid hitting rate limits
    if (current_time - data_cache['dxy']['last_update']) < CACHE_DURATION and data_cache['dxy']['data']:
        print("DXY: Using cached data")
        return data_cache['dxy']['data']
    
    api_key = "d1if0rhr01qhsrhf65b0d1if0rhr01qhsrhf65bg"  # Your Finnhub API key
    
    # Try direct DXY first, fallback to calculation if needed
    symbols_to_try = [
        "OANDA:DXY_USD",  # Direct DXY if available
        "FOREX:DXY",      # Alternative DXY symbol
        "IC MARKETS:DXY"  # Another potential DXY symbol
    ]
    
    dxy_data = []
    
    for symbol in symbols_to_try:
        url = f"https://finnhub.io/api/v1/forex/candle?symbol={symbol}&resolution=1&count=5&token={api_key}"
        print(f"DXY: Trying symbol {symbol}...")
        
        data = make_api_request_with_retry(url)
        
        if data and "t" in data and data["t"]:
            print(f"DXY: Success with symbol {symbol}")
            for i in range(len(data["t"])):
                try:
                    dxy_data.append({
                        "Datetime": pd.to_datetime(data["t"][i], unit='s'),
                        "Open": data["o"][i],
                        "High": data["h"][i],
                        "Low": data["l"][i],
                        "Close": data["c"][i],
                    })
                except (ValueError, IndexError) as e:
                    print(f"DXY: Error parsing data point: {e}")
                    continue
            break
    
    # If direct DXY failed, calculate from major FX pairs
    if not dxy_data:
        print("DXY: Direct symbols failed, attempting calculation from FX pairs...")
        dxy_data = calculate_dxy_from_fx_pairs(api_key)
    
    # Update cache
    if dxy_data:
        data_cache['dxy']['data'] = dxy_data
        data_cache['dxy']['last_update'] = current_time
        print(f"DXY: Cached {len(dxy_data)} data points")
    else:
        print("DXY: No data available, using cached data if available")
        return data_cache['dxy']['data']

    return dxy_data

def calculate_dxy_from_fx_pairs(api_key):
    """Calculate DXY manually from major FX pairs if direct DXY is not available"""
    # DXY is calculated as: DXY = 50.14348112 × (EUR/USD)^(-0.576) × (USD/JPY)^(0.136) × (GBP/USD)^(-0.119) × (USD/CAD)^(0.091) × (USD/SEK)^(0.042) × (USD/CHF)^(0.036)
    
    pairs_data = {}
    major_pairs = [
        ("OANDA:EUR_USD", "eurusd"),
        ("OANDA:USD_JPY", "usdjpy"), 
        ("OANDA:GBP_USD", "gbpusd"),
        ("OANDA:USD_CAD", "usdcad"),
        ("OANDA:USD_SEK", "usdsek"),
        ("OANDA:USD_CHF", "usdchf")
    ]
    
    print("DXY Calculation: Fetching major FX pairs...")
    
    for symbol, pair_name in major_pairs:
        url = f"https://finnhub.io/api/v1/forex/candle?symbol={symbol}&resolution=1&count=5&token={api_key}"
        data = make_api_request_with_retry(url)
        
        if data and "t" in data and data["t"]:
            pairs_data[pair_name] = data
            print(f"DXY Calculation: Got {pair_name} data")
        else:
            print(f"DXY Calculation: Failed to get {pair_name} data")
    
    # Check if we have enough data to calculate DXY
    required_pairs = ["eurusd", "usdjpy"]  # Minimum required for basic calculation
    if not all(pair in pairs_data for pair in required_pairs):
        print("DXY Calculation: Insufficient data for calculation")
        return []
    
    # Simplified DXY calculation using available pairs
    try:
        dxy_calculated = []
        timestamps = pairs_data["eurusd"]["t"]
        
        for i in range(len(timestamps)):
            # Simplified calculation (this is a rough approximation)
            eur_usd = pairs_data["eurusd"]["c"][i]  # Close price
            usd_jpy = pairs_data.get("usdjpy", {}).get("c", [100])[i] if i < len(pairs_data.get("usdjpy", {}).get("c", [])) else 100
            
            # Very simplified DXY approximation: higher when USD is stronger
            dxy_value = 100 * (usd_jpy / 100) / eur_usd
            
            dxy_calculated.append({
                "Datetime": pd.to_datetime(timestamps[i], unit='s'),
                "Open": dxy_value * 0.99,   # Approximate OHLC
                "High": dxy_value * 1.01,
                "Low": dxy_value * 0.98,
                "Close": dxy_value,
            })
        
        print(f"DXY Calculation: Successfully calculated {len(dxy_calculated)} points")
        return dxy_calculated
        
    except Exception as e:
        print(f"DXY Calculation: Error in calculation: {e}")
        return []

def get_usdeur_data():
    """Get EUR/USD 1-minute interval data (5 points for near-live feel)"""
    # Use Twelve Data for EUR/USD as it's more reliable for FX
    api_key = "c6137f97a46c4ae69a47635e66d669da"  # Your Twelve Data API key
    url = f"https://api.twelvedata.com/time_series?symbol=EUR/USD&interval=1min&outputsize=5&apikey={api_key}"
    
    print(f"EUR/USD: Fetching data from Twelve Data...")
    data = make_api_request_with_retry(url)

    if not data or "values" not in data:
        print("EUR/USD: No data from Twelve Data, trying Finnhub...")
        # Fallback to Finnhub
        finnhub_key = "d1if0rhr01qhsrhf65b0d1if0rhr01qhsrhf65bg"
        fallback_url = f"https://finnhub.io/api/v1/forex/candle?symbol=OANDA:EUR_USD&resolution=1&count=5&token={finnhub_key}"
        fallback_data = make_api_request_with_retry(fallback_url)
        
        if fallback_data and "t" in fallback_data and fallback_data["t"]:
            fx_data = []
            for i in range(len(fallback_data["t"])):
                try:
                    fx_data.append({
                        "Datetime": pd.to_datetime(fallback_data["t"][i], unit='s'),
                        "Open": fallback_data["o"][i],
                        "High": fallback_data["h"][i],
                        "Low": fallback_data["l"][i],
                        "Close": fallback_data["c"][i],
                    })
                except (ValueError, IndexError) as e:
                    print(f"EUR/USD: Error parsing Finnhub data: {e}")
                    continue
            print(f"EUR/USD: Success with Finnhub fallback, {len(fx_data)} points")
            return fx_data
        
        return []

    fx_data = []
    for item in reversed(data["values"]):  # Oldest to newest
        try:
            fx_data.append({
                "Datetime": pd.to_datetime(item["datetime"]),
                "Open": float(item["open"]),
                "High": float(item["high"]),
                "Low": float(item["low"]),
                "Close": float(item["close"]),
            })
        except (ValueError, KeyError) as e:
            print(f"EUR/USD: Error parsing Twelve Data point: {e}")
            continue

    print(f"EUR/USD: Success with Twelve Data, {len(fx_data)} points")
    return fx_data
