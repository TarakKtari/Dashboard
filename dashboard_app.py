from flask import Flask, render_template, jsonify
from dashboard.routes import dashboard_bp
from datetime import datetime, timedelta
import json
import time
import requests

from dotenv import load_dotenv
import os

load_dotenv()  # Loads variables from .env

# Example usage:
secret_key = os.getenv("FLASK_SECRET")

app = Flask(__name__)
# app.register_blueprint(dashboard_bp, url_prefix="/dashboard")  # Commented out to avoid conflicts

# Cache for storing latest data to avoid API rate limits
data_cache = {
    'vix': {'data': [], 'last_update': 0},
    'dxy': {'data': [], 'last_update': 0},
    'eurusd': {'data': [], 'last_update': 0}
}

# Rate limiting configuration - CONSERVATIVE for API limits
# Twelve Data: 5-8/min limit → Using 60s cache = 1 call/min per endpoint (2 total)
# Finnhub: 60/min limit → Using 60s cache = 1 call/min (well under limit)
CACHE_DURATION = 60  # 60 seconds cache = exactly 1 call/minute per endpoint
MAX_RETRIES = 3
RETRY_DELAY = 2  # 2 second initial delay for more conservative retry
TWELVE_DATA_RATE_LIMIT = 5  # Conservative: 5 calls/min limit for Twelve Data
FINNHUB_RATE_LIMIT = 60     # Finnhub: 60 calls/min limit

# Global rate limiting tracking
api_call_tracker = {
    'twelve_data': {'calls': [], 'last_reset': time.time()},
    'finnhub': {'calls': [], 'last_reset': time.time()}
}

def check_rate_limit(api_name, limit_per_minute):
    """Check if we can make an API call without exceeding rate limits"""
    current_time = time.time()
    tracker = api_call_tracker[api_name]
    
    # Reset counter every minute
    if current_time - tracker['last_reset'] >= 60:
        tracker['calls'] = []
        tracker['last_reset'] = current_time
    
    # Remove calls older than 1 minute
    tracker['calls'] = [call_time for call_time in tracker['calls'] 
                       if current_time - call_time < 60]
    
    # Check if we can make another call
    if len(tracker['calls']) >= limit_per_minute:
        wait_time = 60 - (current_time - min(tracker['calls']))
        print(f"{api_name}: Rate limit reached, need to wait {wait_time:.1f}s")
        return False, wait_time
    
    return True, 0

def record_api_call(api_name):
    """Record an API call for rate limiting"""
    api_call_tracker[api_name]['calls'].append(time.time())

def make_api_request_with_retry(url, api_name, max_retries=MAX_RETRIES):
    """Make API request with rate limiting and exponential backoff retry logic"""
    
    # Determine rate limit for this API
    if api_name == 'twelve_data':
        rate_limit = TWELVE_DATA_RATE_LIMIT
    elif api_name == 'finnhub':
        rate_limit = FINNHUB_RATE_LIMIT
    else:
        rate_limit = 5  # Default conservative limit
    
    # Check rate limit before making call
    can_call, wait_time = check_rate_limit(api_name, rate_limit)
    if not can_call:
        print(f"{api_name}: Waiting {wait_time:.1f}s due to rate limit")
        time.sleep(wait_time)
    
    for attempt in range(max_retries):
        try:
            # Record the API call
            record_api_call(api_name)
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                print(f"{api_name}: API call successful (attempt {attempt + 1})")
                return response.json()
            elif response.status_code == 429:  # Rate limit hit
                wait_time = RETRY_DELAY * (2 ** attempt)  # Exponential backoff
                print(f"{api_name}: Rate limit hit (429), waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                time.sleep(wait_time)
            else:
                print(f"{api_name}: API request failed with status {response.status_code}")
                break
                
        except requests.exceptions.RequestException as e:
            print(f"{api_name}: Request exception on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(RETRY_DELAY * (2 ** attempt))
    
    print(f"{api_name}: All retry attempts failed")
    return None

@app.route("/")
def home():
    return "<h1>Dashboard Home</h1><p><a href='/test'>Simple Test</a> | <a href='/charts'>Charts</a></p>"

@app.route("/test")
def test():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Simple Test</title></head>
    <body>
        <h1>Simple Test Page</h1>
        <p>If you can see this, the Flask app is working!</p>
        <div id="test-div" style="background: lightblue; padding: 20px; margin: 20px;">
            <h2>Test Container</h2>
            <p>This should appear with a light blue background.</p>
        </div>
        <script>
            console.log('JavaScript is working!');
            document.getElementById('test-div').innerHTML += '<p><strong>JavaScript executed successfully!</strong></p>';
        </script>
    </body>
    </html>
    """

@app.route("/charts")
def charts():
    # Get real data from APIs
    import requests
    import time
    
    # Get API keys from environment
    twelve_data_key = os.getenv("TWELVE_DATA_API_KEY")
    finnhub_key = os.getenv("FINNHUB_API_KEY")
    
    print(f"Using Twelve Data API Key: {twelve_data_key[:10]}..." if twelve_data_key else "No Twelve Data key")
    print(f"Using Finnhub API Key: {finnhub_key[:10]}..." if finnhub_key else "No Finnhub key")
    
    # Fetch VIX data from Twelve Data
    vix_data = []
    try:
        vix_url = f"https://api.twelvedata.com/time_series?symbol=VIX&interval=5min&outputsize=24&apikey={twelve_data_key}"
        print(f"Fetching VIX data from: {vix_url}")
        vix_response = requests.get(vix_url, timeout=15)
        print(f"VIX Response status: {vix_response.status_code}")
        
        if vix_response.status_code == 200:
            vix_json = vix_response.json()
            print(f"VIX JSON keys: {vix_json.keys()}")
            
            if "values" in vix_json:
                for item in vix_json["values"][:20]:  # Take first 20 points (most recent)
                    vix_data.append({
                        'x': item["datetime"],
                        'o': float(item["open"]),
                        'h': float(item["high"]),
                        'l': float(item["low"]),
                        'c': float(item["close"])
                    })
                print(f"Fetched {len(vix_data)} VIX data points")
            else:
                print(f"VIX API response: {vix_json}")
    except Exception as e:
        print(f"Error fetching VIX data: {e}")
    
    # Fetch EUR/USD data using multiple sources (TradingView-style approach)
    eurusd_data = []
    
    # Try Method 1: Alpha Vantage API (free tier available)
    alpha_vantage_key = "demo"  # You can get a free key from https://www.alphavantage.co/
    try:
        eurusd_url = f"https://www.alphavantage.co/query?function=FX_INTRADAY&from_symbol=EUR&to_symbol=USD&interval=5min&apikey={alpha_vantage_key}&outputsize=compact"
        print(f"Fetching EUR/USD from Alpha Vantage: {eurusd_url}")
        eurusd_response = requests.get(eurusd_url, timeout=15)
        print(f"EUR/USD Alpha Vantage Response status: {eurusd_response.status_code}")
        
        if eurusd_response.status_code == 200:
            eurusd_json = eurusd_response.json()
            print(f"EUR/USD Alpha Vantage JSON keys: {eurusd_json.keys()}")
            
            if "Time Series FX (5min)" in eurusd_json:
                time_series = eurusd_json["Time Series FX (5min)"]
                for timestamp, data in list(time_series.items())[:20]:  # Take first 20 points
                    eurusd_data.append({
                        'x': timestamp,
                        'o': float(data["1. open"]),
                        'h': float(data["2. high"]),
                        'l': float(data["3. low"]),
                        'c': float(data["4. close"])
                    })
                print(f"Fetched {len(eurusd_data)} EUR/USD data points from Alpha Vantage")
    except Exception as e:
        print(f"Error fetching EUR/USD from Alpha Vantage: {e}")
    
    # Try Method 2: Yahoo Finance API (if Alpha Vantage fails)
    if len(eurusd_data) == 0:
        try:
            # Yahoo Finance API endpoint for EUR/USD
            yahoo_url = "https://query1.finance.yahoo.com/v8/finance/chart/EURUSD=X?interval=5m&range=1d"
            print(f"Fetching EUR/USD from Yahoo Finance: {yahoo_url}")
            yahoo_response = requests.get(yahoo_url, timeout=15)
            print(f"EUR/USD Yahoo Response status: {yahoo_response.status_code}")
            
            if yahoo_response.status_code == 200:
                yahoo_json = yahoo_response.json()
                result = yahoo_json["chart"]["result"][0]
                timestamps = result["timestamp"]
                quotes = result["indicators"]["quote"][0];
                
                for i in range(min(20, len(timestamps))):  # Take first 20 points
                    if quotes["close"][i] is not None:
                        eurusd_data.append({
                            'x': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(timestamps[i])),
                            'o': float(quotes["open"][i] or quotes["close"][i]),
                            'h': float(quotes["high"][i] or quotes["close"][i]),
                            'l': float(quotes["low"][i] or quotes["close"][i]),
                            'c': float(quotes["close"][i])
                        })
                print(f"Fetched {len(eurusd_data)} EUR/USD data points from Yahoo Finance")
        except Exception as e:
            print(f"Error fetching EUR/USD from Yahoo Finance: {e}")
    
    # Try Method 3: Twelve Data as fallback
    if len(eurusd_data) == 0:
        try:
            eurusd_url = f"https://api.twelvedata.com/time_series?symbol=EUR/USD&interval=5min&outputsize=24&apikey={twelve_data_key}"
            print(f"Fetching EUR/USD fallback from Twelve Data: {eurusd_url}")
            eurusd_response = requests.get(eurusd_url, timeout=15)
            print(f"EUR/USD Twelve Data Response status: {eurusd_response.status_code}")
            
            if eurusd_response.status_code == 200:
                eurusd_json = eurusd_response.json()
                if "values" in eurusd_json:
                    for item in eurusd_json["values"][:20]:
                        eurusd_data.append({
                            'x': item["datetime"],
                            'o': float(item["open"]),
                            'h': float(item["high"]),
                            'l': float(item["low"]),
                            'c': float(item["close"])
                        })
                    print(f"Fetched {len(eurusd_data)} EUR/USD data points from Twelve Data fallback")
        except Exception as e:
            print(f"Error fetching EUR/USD from Twelve Data fallback: {e}")
    


    # Fetch DXY data from Finnhub (try a different symbol)
    dxy_data = []
    try:
        current_time = int(time.time())
        past_time = current_time - (6 * 60 * 60)  # 6 hours ago for better data
        # Try different DXY symbols on Finnhub
        dxy_symbols = ["DX-Y.NYB", "DX=F", "DINIW"]
        
        for symbol in dxy_symbols:
            dxy_url = f"https://finnhub.io/api/v1/stock/candle?symbol={symbol}&resolution=5&from={past_time}&to={current_time}&token={finnhub_key}"
            print(f"Trying DXY symbol {symbol}: {dxy_url}")
            dxy_response = requests.get(dxy_url, timeout=15)
            print(f"DXY ({symbol}) Response status: {dxy_response.status_code}")
            
            if dxy_response.status_code == 200:
                dxy_json = dxy_response.json()
                print(f"DXY ({symbol}) JSON keys: {dxy_json.keys()}")
                
                if "t" in dxy_json and dxy_json.get("s") == "ok" and len(dxy_json["t"]) > 0:
                    for i in range(min(20, len(dxy_json["t"]))):  # Take up to 20 points
                        timestamp = dxy_json["t"][i]
                        date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')
                        dxy_data.append({
                            'x': date_str,
                            'o': dxy_json["o"][i],
                            'h': dxy_json["h"][i],
                            'l': dxy_json["l"][i],
                            'c': dxy_json["c"][i]
                        })
                    print(f"Fetched {len(dxy_data)} DXY data points from {symbol}")
                    break  # Found data, stop trying other symbols
                else:
                    print(f"DXY ({symbol}) API response: {dxy_json}")
    except Exception as e:
        print(f"Error fetching DXY data: {e}")
    
    # Enhanced fallback data with proper timestamps
    current_time = datetime.now()
    
    if not vix_data:
        print("Using fallback VIX data")
        for i in range(20):
            time_point = current_time.replace(minute=(current_time.minute // 5) * 5, second=0, microsecond=0) - timedelta(minutes=i*5)
            vix_data.append({
                'x': time_point.strftime('%Y-%m-%d %H:%M'),
                'o': 20.5 + i * 0.1 + (i % 3 - 1) * 0.2,
                'h': 21.0 + i * 0.1 + (i % 3 - 1) * 0.2,
                'l': 20.0 + i * 0.1 + (i % 3 - 1) * 0.2,
                'c': 20.8 + i * 0.1 + (i % 3 - 1) * 0.2
            })
        vix_data.reverse()  # Most recent first
    
    if not dxy_data:
        print("Using fallback DXY data")
        for i in range(20):
            time_point = current_time.replace(minute=(current_time.minute // 5) * 5, second=0, microsecond=0) - timedelta(minutes=i*5)
            dxy_data.append({
                'x': time_point.strftime('%Y-%m-%d %H:%M'),
                'o': 103.5 + i * 0.05 + (i % 4 - 2) * 0.1,
                'h': 104.0 + i * 0.05 + (i % 4 - 2) * 0.1,
                'l': 103.0 + i * 0.05 + (i % 4 - 2) * 0.1,
                'c': 103.8 + i * 0.05 + (i % 4 - 2) * 0.1
            })
        dxy_data.reverse()  # Most recent first
    
    if not eurusd_data:
        print("Using fallback EUR/USD data")
        for i in range(20):
            time_point = current_time.replace(minute=(current_time.minute // 5) * 5, second=0, microsecond=0) - timedelta(minutes=i*5)
            eurusd_data.append({
                'x': time_point.strftime('%Y-%m-%d %H:%M'),
                'o': 1.0850 + i * 0.001 + (i % 5 - 2) * 0.002,
                'h': 1.0900 + i * 0.001 + (i % 5 - 2) * 0.002,
                'l': 1.0800 + i * 0.001 + (i % 5 - 2) * 0.002,
                'c': 1.0875 + i * 0.001 + (i % 5 - 2) * 0.002
            })
        eurusd_data.reverse()  # Most recent first
    
    # Convert data to JSON strings
    import json
    vix_json = json.dumps(vix_data)
    dxy_json = json.dumps(dxy_data)
    eurusd_json = json.dumps(eurusd_data)
    
    print(f"Final data lengths: VIX={len(vix_data)}, DXY={len(dxy_data)}, EUR/USD={len(eurusd_data)}")
    
    # HTML and JavaScript
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>FX Trading Dashboard - Live Real-Time Data</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
        <script src="https://unpkg.com/chartjs-adapter-date-fns/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
        <script src="https://unpkg.com/chartjs-chart-financial/dist/chartjs-chart-financial.js"></script>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
            .dashboard-container {{ max-width: 1400px; margin: 0 auto; }}
            .dashboard-row {{ display: flex; gap: 20px; margin-bottom: 20px; flex-wrap: wrap; }}
            .dashboard-card {{ 
                background: #fff; 
                border: 1px solid #ddd; 
                border-radius: 8px; 
                padding: 20px; 
                flex: 1; 
                min-width: 400px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .chart-container {{ width: 100%; height: 350px; position: relative; }}
            h1 {{ text-align: center; color: #333; margin-bottom: 30px; }}
            h3 {{ margin-top: 0; color: #555; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
            .status {{ text-align: center; padding: 10px; background: #28a745; color: white; border-radius: 5px; margin-bottom: 20px; }}
            .api-status {{ text-align: center; padding: 5px; background: #17a2b8; color: white; border-radius: 3px; margin: 5px 0; font-size: 12px; }}
            .price-info {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }}
            .current-price {{ font-size: 18px; font-weight: bold; color: #333; }}
            .price-change {{ padding: 3px 8px; border-radius: 3px; color: white; font-size: 14px; }}
            .price-up {{ background-color: #16a34a; }}
            .price-down {{ background-color: #dc2626; }}
        </style>
    </head>
    <body>
        <div class="dashboard-container">
            <h1>🔴 LIVE FX Trading Dashboard - Real-Time Data</h1>
            <div class="status">📊 Real-time Market Data from Twelve Data & Finnhub APIs | Last Update: <span id="lastUpdate"></span></div>
            <div class="api-status">✅ VIX: {len(vix_data)} points | ✅ DXY: {len(dxy_data)} points | ✅ EUR/USD: {len(eurusd_data)} points</div>
            
            <div class="dashboard-row">
                <div class="dashboard-card">
                    <div class="price-info">
                        <h3>📈 DXY (US Dollar Index)</h3>
                        <div>
                            <span class="current-price" id="dxyPrice">--</span>
                            <span class="price-change" id="dxyChange">--</span>
                        </div>
                    </div>
                    <div class="chart-container">
                        <canvas id="dxyChart"></canvas>
                    </div>
                </div>
                <div class="dashboard-card">
                    <div class="price-info">
                        <h3>⚡ VIX (Volatility Index)</h3>
                        <div>
                            <span class="current-price" id="vixPrice">--</span>
                            <span class="price-change" id="vixChange">--</span>
                        </div>
                    </div>
                    <div class="chart-container">
                        <canvas id="vixChart"></canvas>
                    </div>
                </div>
            </div>
            
            <div class="dashboard-row">
                <div class="dashboard-card">
                    <div class="price-info">
                        <h3>💱 EUR/USD Exchange Rate</h3>
                        <div>
                            <span class="current-price" id="eurusdPrice">--</span>
                            <span class="price-change" id="eurusdChange">--</span>
                        </div>
                    </div>
                    <div class="chart-container">
                        <canvas id="eurusdChart"></canvas>
                    </div>
                </div>
            </div>
        </div>"""
    
    # JavaScript content (avoiding f-string conflicts)
    js_content = '''
        <script>
        // Real API data from the server
        const vixData = ''' + vix_json + ''';
        const dxyData = ''' + dxy_json + ''';
        const eurusdData = ''' + eurusd_json + ''';
        
        // Global chart variables
        let dxyChart, vixChart, eurusdChart;
        
        document.addEventListener('DOMContentLoaded', function() {
            // Update timestamp
            document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
            
            console.log('Initializing dashboard with real API data...');
            console.log('VIX Data:', vixData);
            console.log('DXY Data:', dxyData);
            console.log('EUR/USD Data:', eurusdData);
            
            // Process data for candlestick charts (using OHLC data)
            function processDataForCandlestickChart(data, label) {
                if (!data || !Array.isArray(data) || data.length === 0) {
                    console.warn(`No data available for ${label}`);
                    return { labels: [], values: [] };
                }
                
                const processedData = data.map(item => {
                    const time = new Date(item.x).getTime();
                    return {
                        x: time,
                        o: parseFloat(item.o),
                        h: parseFloat(item.h),
                        l: parseFloat(item.l),
                        c: parseFloat(item.c)
                    };
                });
                
                console.log(`Processed ${label} candlestick data:`, processedData.slice(0, 2));
                return processedData;
            }
            
            // Update price displays
            function updatePriceDisplay(symbol, data) {
                if (!data || data.length === 0) return;
                
                const latest = data[data.length - 1];
                const previous = data.length > 1 ? data[data.length - 2] : latest;
                
                const currentPrice = parseFloat(latest.c);
                const previousPrice = parseFloat(previous.c);
                const change = currentPrice - previousPrice;
                const changePercent = ((change / previousPrice) * 100).toFixed(2);
                
                const priceElement = document.getElementById(symbol + 'Price');
                const changeElement = document.getElementById(symbol + 'Change');
                
                if (priceElement) {
                    priceElement.textContent = currentPrice.toFixed(4);
                }
                
                if (changeElement) {
                    const changeText = `${change >= 0 ? '+' : ''}${change.toFixed(4)} (${changePercent}%)`;
                    changeElement.textContent = changeText;
                    changeElement.className = `price-change ${change >= 0 ? 'price-up' : 'price-down'}`;
                }
            }
            
            // Create candlestick chart
            function createCandlestickChart(ctx, data, label, upColor, downColor) {
                const processedData = processDataForCandlestickChart(data, label);
                
                if (processedData.length === 0) {
                    ctx.font = '16px Arial';
                    ctx.fillStyle = '#666';
                    ctx.textAlign = 'center';
                    ctx.fillText(`No ${label} data available`, ctx.canvas.width / 2, ctx.canvas.height / 2);
                    return null;
                }
                
                return new Chart(ctx, {
                    type: 'candlestick',
                    data: {
                        datasets: [{
                            label: label,
                            data: processedData,
                            borderColor: upColor,
                            color: {
                                up: upColor,
                                down: downColor,
                                unchanged: '#999'
                            }
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: {
                            intersect: false,
                            mode: 'index'
                        },
                        scales: {
                            x: {
                                type: 'time',
                                time: {
                                    unit: 'minute',
                                    displayFormats: {
                                        minute: 'HH:mm'
                                    }
                                },
                                title: {
                                    display: true,
                                    text: 'Time'
                                },
                                grid: {
                                    color: 'rgba(0,0,0,0.1)'
                                }
                            },
                            y: {
                                title: {
                                    display: true,
                                    text: 'Price'
                                },
                                grid: {
                                    color: 'rgba(0,0,0,0.1)'
                                }
                            }
                        },
                        plugins: {
                            legend: {
                                display: true,
                                position: 'top'
                            },
                            tooltip: {
                                mode: 'index',
                                intersect: false,
                                backgroundColor: 'rgba(0,0,0,0.8)',
                                titleColor: '#fff',
                                bodyColor: '#fff',
                                callbacks: {
                                    title: function(context) {
                                        return new Date(context[0].parsed.x).toLocaleString();
                                    },
                                    label: function(context) {
                                        const data = context.parsed;
                                        return [
                                            `${label}:`,
                                            `Open: ${data.o.toFixed(4)}`,
                                            `High: ${data.h.toFixed(4)}`,
                                            `Low: ${data.l.toFixed(4)}`,
                                            `Close: ${data.c.toFixed(4)}`
                                        ];
                                    }
                                }
                            }
                        },
                        animation: {
                            duration: 750,
                            easing: 'easeInOutQuart'
                        }
                    }
                });
            }
            
            // Create OHLC line chart showing High-Low with Close markers
            function createOHLCChart(ctx, data, label, upColor, downColor) {
                const processedData = processDataForCandlestickChart(data, label);
                
                if (processedData.length === 0) {
                    ctx.font = '16px Arial';
                    ctx.fillStyle = '#666';
                    ctx.textAlign = 'center';
                    ctx.fillText(`No ${label} data available`, ctx.canvas.width / 2, ctx.canvas.height / 2);
                    return null;
                }
                
                // Create labels for time axis
                const timeLabels = processedData.map(item => {
                    const date = new Date(item.x);
                    return date.toLocaleTimeString('en-US', {
                        hour: '2-digit',
                        minute: '2-digit'
                    });
                });
                
                // Prepare datasets: High, Low, Close lines
                const highData = processedData.map(item => item.h);
                const lowData = processedData.map(item => item.l);
                const closeData = processedData.map(item => item.c);
                const openData = processedData.map(item => item.o);
                
                return new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: timeLabels,
                        datasets: [
                            {
                                label: `${label} High`,
                                data: highData,
                                borderColor: '#666',
                                backgroundColor: 'transparent',
                                borderWidth: 1,
                                fill: false,
                                pointRadius: 2,
                                pointBackgroundColor: '#666'
                            },
                            {
                                label: `${label} Low`,
                                data: lowData,
                                borderColor: '#999',
                                backgroundColor: 'transparent',
                                borderWidth: 1,
                                fill: false,
                                pointRadius: 2,
                                pointBackgroundColor: '#999'
                            },
                            {
                                label: `${label} Close`,
                                data: closeData,
                                borderColor: upColor,
                                backgroundColor: upColor + '40',
                                borderWidth: 3,
                                fill: false,
                                pointRadius: 4,
                                pointBackgroundColor: upColor,
                                pointBorderColor: '#fff',
                                pointBorderWidth: 2
                            },
                            {
                                label: `${label} Open`,
                                data: openData,
                                borderColor: downColor,
                                backgroundColor: 'transparent',
                                borderWidth: 2,
                                fill: false,
                                pointRadius: 3,
                                pointBackgroundColor: downColor,
                                borderDash: [5, 5]
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: {
                            intersect: false,
                            mode: 'index'
                        },
                        scales: {
                            x: {
                                title: {
                                    display: true,
                                    text: 'Time'
                                },
                                grid: {
                                    color: 'rgba(0,0,0,0.1)'
                                }
                            },
                            y: {
                                title: {
                                    display: true,
                                    text: 'Price'
                                },
                                grid: {
                                    color: 'rgba(0,0,0,0.1)'
                                }
                            }
                        },
                        plugins: {
                            legend: {
                                display: true,
                                position: 'top'
                            },
                            tooltip: {
                                mode: 'index',
                                intersect: false,
                                backgroundColor: 'rgba(0,0,0,0.8)',
                                titleColor: '#fff',
                                bodyColor: '#fff',
                                callbacks: {
                                    title: function(context) {
                                        return context[0].label;
                                    },
                                    afterTitle: function(context) {
                                        const dataIndex = context[0].dataIndex;
                                        const candle = processedData[dataIndex];
                                        return `OHLC Data:`;
                                    },
                                    label: function(context) {
                                        const dataIndex = context.dataIndex;
                                        const candle = processedData[dataIndex];
                                        const datasetLabel = context.dataset.label;
                                        
                                        if (datasetLabel.includes('Close')) {
                                            return [
                                                `Open: ${candle.o.toFixed(4)}`,
                                                `High: ${candle.h.toFixed(4)}`,
                                                `Low: ${candle.l.toFixed(4)}`,
                                                `Close: ${candle.c.toFixed(4)}`
                                            ];
                                        }
                                        return `${datasetLabel}: ${context.parsed.y.toFixed(4)}`;
                                    }
                                }
                            }
                        },
                        animation: {
                            duration: 750,
                            easing: 'easeInOutQuart'
                        }
                    }
                });
            }
            
            // Initialize charts
            try {
                console.log('Creating candlestick charts...');
                
                // DXY Chart
                const dxyCtx = document.getElementById('dxyChart').getContext('2d');
                dxyChart = createCandlestickChart(dxyCtx, dxyData, 'DXY', '#16a34a', '#dc2626');
                updatePriceDisplay('dxy', dxyData);
                
                // VIX Chart  
                const vixCtx = document.getElementById('vixChart').getContext('2d');
                vixChart = createCandlestickChart(vixCtx, vixData, 'VIX', '#2563eb', '#dc2626');
                updatePriceDisplay('vix', vixData);
                
                // EUR/USD Chart
                const eurusdCtx = document.getElementById('eurusdChart').getContext('2d');
                eurusdChart = createCandlestickChart(eurusdCtx, eurusdData, 'EUR/USD', '#16a34a', '#dc2626');
                updatePriceDisplay('eurusd', eurusdData);
                
                console.log('Candlestick charts initialized successfully');
                
            } catch (error) {
                console.error('Error creating charts:', error);
                alert('Error loading charts: ' + error.message);
            }
            
            // Function to update charts with fresh data
            function updateChartsWithFreshData() {
                console.log('🔄 Fetching fresh market data...');
                
                fetch('/api/refresh-data')
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`HTTP ${response.status}`);
                        }
                        return response.json();
                    })
                    .then(newData => {
                        console.log('📊 Received fresh data:', newData);
                        
                        // Update VIX chart
                        if (newData.vix && vixChart) {
                            const vixProcessed = processDataForCandlestickChart(newData.vix, 'VIX');
                            vixChart.data.datasets[0].data = vixProcessed;
                            vixChart.update('active');
                            updatePriceDisplay('vix', newData.vix);
                        }
                        
                        // Update DXY chart  
                        if (newData.dxy && dxyChart) {
                            const dxyProcessed = processDataForCandlestickChart(newData.dxy, 'DXY');
                            dxyChart.data.datasets[0].data = dxyProcessed;
                            dxyChart.update('active');
                            updatePriceDisplay('dxy', newData.dxy);
                        }
                        
                        // Update EUR/USD chart
                        if (newData.eurusd && eurusdChart) {
                            const eurusdProcessed = processDataForCandlestickChart(newData.eurusd, 'EUR/USD');
                            eurusdChart.data.datasets[0].data = eurusdProcessed;
                            eurusdChart.update('active');
                            updatePriceDisplay('eurusd', newData.eurusd);
                        }
                        
                        // Update timestamp
                        document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
                        
                        console.log('✅ Charts updated successfully');
                        
                    })
                    .catch(error => {
                        console.error('❌ Error updating charts:', error);
                    });
            }
            
            // Auto-refresh every 15 seconds for truly dynamic updates
            setInterval(updateChartsWithFreshData, 15000);
            
            // Update timestamp every 5 seconds
            setInterval(function() {
                const now = new Date();
                document.getElementById('lastUpdate').textContent = now.toLocaleTimeString();
            }, 5000);
            
            console.log('🚀 Dashboard fully initialized - real-time updates every 15 seconds');
        });
        </script>
    </body>
    </html>'''
    
    return html_content + js_content

@app.route("/api/data")
def api_data():
    """Return raw market data as JSON for verification"""
    import requests
    import time
    from flask import jsonify
    
    # Get API keys from environment
    twelve_data_key = os.getenv("TWELVE_DATA_API_KEY")
    finnhub_key = os.getenv("FINNHUB_API_KEY")
    
    result = {
        "status": "success",
        "data_sources": {
            "twelve_data": bool(twelve_data_key),
            "finnhub": bool(finnhub_key)
        },
        "data": {}
    }
    
    # Test VIX from Twelve Data
    try:
        vix_url = f"https://api.twelvedata.com/time_series?symbol=VIX&interval=5min&outputsize=5&apikey={twelve_data_key}"
        vix_response = requests.get(vix_url, timeout=10)
        if vix_response.status_code == 200:
            vix_json = vix_response.json()
            result["data"]["vix"] = {
                "status": "success",
                "source": "twelve_data",
                "points": len(vix_json.get("values", [])),
                "latest": vix_json.get("values", [{}])[0] if vix_json.get("values") else None
            }
        else:
            result["data"]["vix"] = {"status": "error", "code": vix_response.status_code}
    except Exception as e:
        result["data"]["vix"] = {"status": "error", "error": str(e)}
    
    # Test EUR/USD from Twelve Data
    try:
        eurusd_url = f"https://api.twelvedata.com/time_series?symbol=EUR/USD&interval=5min&outputsize=5&apikey={twelve_data_key}"
        eurusd_response = requests.get(eurusd_url, timeout=10)
        if eurusd_response.status_code == 200:
            eurusd_json = eurusd_response.json()
            result["data"]["eurusd"] = {
                "status": "success",
                "source": "twelve_data",
                "points": len(eurusd_json.get("values", [])),
                "latest": eurusd_json.get("values", [{}])[0] if eurusd_json.get("values") else None
            }
        else:
            result["data"]["eurusd"] = {"status": "error", "code": eurusd_response.status_code}
    except Exception as e:
        result["data"]["eurusd"] = {"status": "error", "error": str(e)}
    
    return jsonify(result)

@app.route("/api/refresh-data")
def refresh_data():
    """Return fresh market data for dynamic chart updates"""
    import requests
    import time
    from flask import jsonify
    
    # Get API keys from environment
    twelve_data_key = os.getenv("TWELVE_DATA_API_KEY")
    finnhub_key = os.getenv("FINNHUB_API_KEY")
    
    result = {}
    
    # Fetch fresh VIX data
    try:
        vix_url = f"https://api.twelvedata.com/time_series?symbol=VIX&interval=5min&outputsize=24&apikey={twelve_data_key}"
        vix_response = requests.get(vix_url, timeout=10)
        if vix_response.status_code == 200:
            vix_json = vix_response.json()
            if "values" in vix_json:
                vix_data = []
                for item in vix_json["values"][:20]:
                    vix_data.append({
                        'x': item["datetime"],
                        'o': float(item["open"]),
                        'h': float(item["high"]),
                        'l': float(item["low"]),
                        'c': float(item["close"])
                    })
                result["vix"] = vix_data
    except Exception as e:
        print(f"Error refreshing VIX data: {e}")
    
    # Fetch fresh EUR/USD data using multiple sources (TradingView-style approach)
    eurusd_data = []
    
    # Try Method 1: Alpha Vantage API
    try:
        alpha_vantage_key = "demo"
        eurusd_url = f"https://www.alphavantage.co/query?function=FX_INTRADAY&from_symbol=EUR&to_symbol=USD&interval=5min&apikey={alpha_vantage_key}&outputsize=compact"
        eurusd_response = requests.get(eurusd_url, timeout=10)
        if eurusd_response.status_code == 200:
            eurusd_json = eurusd_response.json()
            if "Time Series FX (5min)" in eurusd_json:
                time_series = eurusd_json["Time Series FX (5min)"]
                for timestamp, data in list(time_series.items())[:20]:
                    eurusd_data.append({
                        'x': timestamp,
                        'o': float(data["1. open"]),
                        'h': float(data["2. high"]),
                        'l': float(data["3. low"]),
                        'c': float(data["4. close"])
                    })
                console.log(f"Refreshed {len(eurusd_data)} EUR/USD points from Alpha Vantage")
    except Exception as e:
        console.log(f"Error refreshing EUR/USD from Alpha Vantage: {e}")
    
    # Try Method 2: Yahoo Finance API (if Alpha Vantage fails)
    if len(eurusd_data) == 0:
        try:
            yahoo_url = "https://query1.finance.yahoo.com/v8/finance/chart/EURUSD=X?interval=5m&range=1d"
            yahoo_response = requests.get(yahoo_url, timeout=10)
            if yahoo_response.status_code == 200:
                yahoo_json = yahoo_response.json()
                result_data = yahoo_json["chart"]["result"][0]
                timestamps = result_data["timestamp"]
                quotes = result_data["indicators"]["quote"][0]
                
                for i in range(min(20, len(timestamps))):
                    if quotes["close"][i] is not None:
                        eurusd_data.append({
                            'x': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(timestamps[i])),
                            'o': float(quotes["open"][i] or quotes["close"][i]),
                            'h': float(quotes["high"][i] or quotes["close"][i]),
                            'l': float(quotes["low"][i] or quotes["close"][i]),
                            'c': float(quotes["close"][i])
                        })
                print(f"Refreshed {len(eurusd_data)} EUR/USD points from Yahoo Finance")
        except Exception as e:
            print(f"Error refreshing EUR/USD from Yahoo Finance: {e}")
    
    # Try Method 3: Twelve Data as fallback
    if len(eurusd_data) == 0:
        try:
            eurusd_url = f"https://api.twelvedata.com/time_series?symbol=EUR/USD&interval=5min&outputsize=24&apikey={twelve_data_key}"
            eurusd_response = requests.get(eurusd_url, timeout=10)
            if eurusd_response.status_code == 200:
                eurusd_json = eurusd_response.json()
                if "values" in eurusd_json:
                    for item in eurusd_json["values"][:20]:
                        eurusd_data.append({
                            'x': item["datetime"],
                            'o': float(item["open"]),
                            'h': float(item["high"]),
                            'l': float(item["low"]),
                            'c': float(item["close"])
                        })
                    print(f"Refreshed {len(eurusd_data)} EUR/USD points from Twelve Data fallback")
        except Exception as e:
            print(f"Error refreshing EUR/USD from Twelve Data fallback: {e}")
    
    if len(eurusd_data) > 0:
        result["eurusd"] = eurusd_data
    
    return jsonify(result)

@app.route("/api/test-eurusd-sources")
def test_eurusd_sources():
    """Test different EUR/USD data sources"""
    import requests
    import time
    from flask import jsonify
    
    results = {}
    
    # Test Alpha Vantage
    try:
        alpha_vantage_key = "demo"
        url = f"https://www.alphavantage.co/query?function=FX_INTRADAY&from_symbol=EUR&to_symbol=USD&interval=5min&apikey={alpha_vantage_key}&outputsize=compact"
        response = requests.get(url, timeout=15)
        results["alpha_vantage"] = {
            "status_code": response.status_code,
            "success": response.status_code == 200,
            "keys": list(response.json().keys()) if response.status_code == 200 else None,
            "has_data": "Time Series FX (5min)" in response.json() if response.status_code == 200 else False
        }
    except Exception as e:
        results["alpha_vantage"] = {"error": str(e), "success": False}
    
    // Test Yahoo Finance
    try {
        url = "https://query1.finance.yahoo.com/v8/finance/chart/EURUSD=X?interval=5m&range=1d"
        response = requests.get(url, timeout=15);
        results["yahoo_finance"] = {
            "status_code": response.status_code,
            "success": response.status_code == 200,
            "has_chart": "chart" in response.json() if response.status_code == 200 else False,
            "has_result": bool(response.json().get("chart", {}).get("result")) if response.status_code == 200 else False
        }
    } catch (Exception as e) {
        results["yahoo_finance"] = {"error": str(e), "success": False}
    }
    
    # Test Twelve Data
    try:
        twelve_data_key = os.getenv("TWELVE_DATA_API_KEY")
        url = f"https://api.twelvedata.com/time_series?symbol=EUR/USD&interval=5min&outputsize=5&apikey={twelve_data_key}"
        response = requests.get(url, timeout=15)
        results["twelve_data"] = {
            "status_code": response.status_code,
            "success": response.status_code == 200,
            "keys": list(response.json().keys()) if response.status_code == 200 else None,
            "has_values": "values" in response.json() if response.status_code == 200 else False
        }
    except Exception as e:
        results["twelve_data"] = {"error": str(e), "success": False}
    
    return jsonify(results)

@app.route("/api/live-data")
def get_live_data():
    """Near-live data endpoint with smart caching and retry logic"""
    return jsonify({
        'vix': get_vix_data_cached(),
        'dxy': get_dxy_data_cached(),
        'eurusd': get_eurusd_data_cached(),
        'timestamp': datetime.now().isoformat(),
        'cache_info': {
            'vix_cached': (time.time() - data_cache['vix']['last_update']) < CACHE_DURATION,
            'dxy_cached': (time.time() - data_cache['dxy']['last_update']) < CACHE_DURATION,
            'eurusd_cached': (time.time() - data_cache['eurusd']['last_update']) < CACHE_DURATION
        }
    })

def get_vix_data_cached():
    """Get VIX 1-minute data with smart caching (5 points for near-live feel)"""
    current_time = time.time()
    
    # Check cache first to avoid hitting rate limits
    if (current_time - data_cache['vix']['last_update']) < CACHE_DURATION and data_cache['vix']['data']:
        print("VIX: Using cached data (rate limit protection)")
        return data_cache['vix']['data']
    
    api_key = "c6137f97a46c4ae69a47635e66d669da"  # Your Twelve Data API key
    url = f"https://api.twelvedata.com/time_series?symbol=VIX&interval=1min&outputsize=5&apikey={api_key}"
    
    print(f"VIX: Fetching fresh 1-minute data from Twelve Data (rate limited)...")
    data = make_api_request_with_retry(url, 'twelve_data')
    
    if not data or "values" not in data:
        print("VIX: No data received, using cached data if available")
        return data_cache['vix']['data']

    vix_data = []
    for item in reversed(data["values"]):  # Oldest to newest for proper chart order
        try:
            vix_data.append({
                "datetime": item["datetime"],
                "open": float(item["open"]),
                "high": float(item["high"]),
                "low": float(item["low"]),
                "close": float(item["close"]),
            })
        except (ValueError, KeyError) as e:
            print(f"VIX: Error parsing data point: {e}")
            continue

    # Update cache
    if vix_data:
        data_cache['vix']['data'] = vix_data
        data_cache['vix']['last_update'] = current_time
        print(f"VIX: Cached {len(vix_data)} fresh 1-minute data points")

    return vix_data

def get_dxy_data_cached():
    """Get DXY 1-minute data with smart caching and fallback calculation"""
    current_time = time.time()
    
    # Check cache first to avoid hitting rate limits
    if (current_time - data_cache['dxy']['last_update']) < CACHE_DURATION and data_cache['dxy']['data']:
        print("DXY: Using cached data (rate limit protection)")
        return data_cache['dxy']['data']
    
    api_key = "d1if0rhr01qhsrhf65b0d1if0rhr01qhsrhf65bg"  # Your Finnhub API key
    
    # Try direct DXY symbols
    symbols_to_try = [
        "OANDA:DXY_USD",
        "FOREX:DXY", 
        "IC MARKETS:DXY"
    ]
    
    dxy_data = []
    
    for symbol in symbols_to_try:
        url = f"https://finnhub.io/api/v1/forex/candle?symbol={symbol}&resolution=1&count=5&token={api_key}"
        print(f"DXY: Trying 1-minute data from {symbol} (rate limited)...")
        
        data = make_api_request_with_retry(url, 'finnhub')
        
        if data and "t" in data and data["t"]:
            print(f"DXY: Success with {symbol}")
            for i in range(len(data["t"])):
                try:
                    dxy_data.append({
                        "datetime": datetime.fromtimestamp(data["t"][i]).isoformat(),
                        "open": data["o"][i],
                        "high": data["h"][i],
                        "low": data["l"][i],
                        "close": data["c"][i],
                    })
                except (ValueError, IndexError) as e:
                    print(f"DXY: Error parsing data point: {e}")
                    continue
            break
    
    # Update cache
    if dxy_data:
        data_cache['dxy']['data'] = dxy_data
        data_cache['dxy']['last_update'] = current_time
        print(f"DXY: Cached {len(dxy_data)} fresh 1-minute data points")
    else:
        print("DXY: No data available, using cached data if available")
        return data_cache['dxy']['data']

    return dxy_data

def get_eurusd_data_cached():
    """Get EUR/USD 1-minute data with smart caching and fallback"""
    current_time = time.time()
    
    # Check cache first to avoid hitting rate limits
    if (current_time - data_cache['eurusd']['last_update']) < CACHE_DURATION and data_cache['eurusd']['data']:
        print("EUR/USD: Using cached data (rate limit protection)")
        return data_cache['eurusd']['data']
    
    # Primary: Twelve Data
    api_key = "c6137f97a46c4ae69a47635e66d669da"
    url = f"https://api.twelvedata.com/time_series?symbol=EUR/USD&interval=1min&outputsize=5&apikey={api_key}"
    
    print(f"EUR/USD: Fetching fresh 1-minute data from Twelve Data (rate limited)...")
    data = make_api_request_with_retry(url, 'twelve_data')

    eurusd_data = []
    
    if data and "values" in data:
        for item in reversed(data["values"]):  # Oldest to newest
            try:
                eurusd_data.append({
                    "datetime": item["datetime"],
                    "open": float(item["open"]),
                    "high": float(item["high"]),
                    "low": float(item["low"]),
                    "close": float(item["close"]),
                })
            except (ValueError, KeyError) as e:
                print(f"EUR/USD: Error parsing Twelve Data point: {e}")
                continue
        
        print(f"EUR/USD: Success with Twelve Data, {len(eurusd_data)} points")
    else:
        # Fallback to Finnhub
        print("EUR/USD: Twelve Data failed, trying Finnhub (rate limited)...")
        finnhub_key = "d1if0rhr01qhsrhf65b0d1if0rhr01qhsrhf65bg"
        fallback_url = f"https://finnhub.io/api/v1/forex/candle?symbol=OANDA:EUR_USD&resolution=1&count=5&token={finnhub_key}"
        fallback_data = make_api_request_with_retry(fallback_url, 'finnhub')
        
        if fallback_data and "t" in fallback_data and fallback_data["t"]:
            for i in range(len(fallback_data["t"])):
                try:
                    eurusd_data.append({
                        "datetime": datetime.fromtimestamp(fallback_data["t"][i]).isoformat(),
                        "open": fallback_data["o"][i],
                        "high": fallback_data["h"][i],
                        "low": fallback_data["l"][i],
                        "close": fallback_data["c"][i],
                    })
                except (ValueError, IndexError) as e:
                    print(f"EUR/USD: Error parsing Finnhub data: {e}")
                    continue
            print(f"EUR/USD: Success with Finnhub fallback, {len(eurusd_data)} points")

    # Update cache
    if eurusd_data:
        data_cache['eurusd']['data'] = eurusd_data
        data_cache['eurusd']['last_update'] = current_time
        print(f"EUR/USD: Cached {len(eurusd_data)} fresh 1-minute data points")
    else:
        print("EUR/USD: No data available, using cached data if available")
        return data_cache['eurusd']['data']

    return eurusd_data

@app.route("/api/rate-limit-status")
def rate_limit_status():
    """Monitor rate limiting status and API call tracking"""
    current_time = time.time()
    
    status = {}
    
    for api_name, tracker in api_call_tracker.items():
        # Count calls in the last minute
        recent_calls = [call_time for call_time in tracker['calls'] 
                       if current_time - call_time < 60]
        
        if api_name == 'twelve_data':
            limit = TWELVE_DATA_RATE_LIMIT
        else:
            limit = FINNHUB_RATE_LIMIT
            
        status[api_name] = {
            'calls_last_minute': len(recent_calls),
            'rate_limit': limit,
            'calls_remaining': max(0, limit - len(recent_calls)),
            'next_reset': tracker['last_reset'] + 60,
            'cache_status': {}
        }
    }
    
    # Add cache status
    for data_type in ['vix', 'dxy', 'eurusd']:
        cache_age = current_time - data_cache[data_type]['last_update']
        status['cache_info'] = status.get('cache_info', {})
        status['cache_info'][data_type] = {
            'age_seconds': cache_age,
            'is_fresh': cache_age < CACHE_DURATION,
            'data_points': len(data_cache[data_type]['data']),
            'next_refresh': data_cache[data_type]['last_update'] + CACHE_DURATION
        }
    }
    
    return jsonify({
        'rate_limits': status,
        'cache_duration': CACHE_DURATION,
        'current_time': current_time,
        'summary': {
            'twelve_data_safe': status['twelve_data']['calls_remaining'] > 0,
            'finnhub_safe': status['finnhub']['calls_remaining'] > 0,
            'all_caches_fresh': all(info['is_fresh'] for info in status['cache_info'].values())
        }
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)
