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
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>FX Trading Dashboard</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            .dashboard-container { max-width: 1200px; margin: 0 auto; padding: 20px; }
            .dashboard-row { display: flex; gap: 20px; margin-bottom: 20px; }
            .dashboard-card { background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 15px; flex: 1; }
            .chart-container { width: 100%; height: 300px; }
            h1 { text-align: center; color: #333; }
            h3 { margin-top: 0; color: #555; }
        </style>
    </head>
    <body>
        <div class="dashboard-container">
            <h1>FX Trading Dashboard – Admin View</h1>
            
            <div class="dashboard-row">
                <div class="dashboard-card">
                    <h3>DXY (US Dollar Index)</h3>
                    <div class="chart-container">
                        <canvas id="dxyChart"></canvas>
                    </div>
                </div>
                <div class="dashboard-card">
                    <h3>VIX (CBOE Volatility Index)</h3>
                    <div class="chart-container">
                        <canvas id="vixChart"></canvas>
                    </div>
                </div>
            </div>
            
            <div class="dashboard-row">
                <div class="dashboard-card">
                    <h3>USD/EUR Exchange Rate</h3>
                    <div class="chart-container">
                        <canvas id="usdeurChart"></canvas>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
        document.addEventListener('DOMContentLoaded', function() {
            // Mock data for charts
            const timeLabels = ['10:00', '10:05', '10:10', '10:15', '10:20', '10:25', '10:30', '10:35', '10:40', '10:45'];
            
            // DXY Chart
            const dxyCtx = document.getElementById('dxyChart').getContext('2d');
            new Chart(dxyCtx, {
                type: 'line',
                data: {
                    labels: timeLabels,
                    datasets: [{
                        label: 'DXY',
                        data: [103.5, 103.7, 103.4, 103.8, 103.9, 104.1, 103.6, 103.8, 104.0, 103.7],
                        borderColor: '#2563eb',
                        backgroundColor: 'rgba(37, 99, 235, 0.1)',
                        fill: false,
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: false }
                    }
                }
            });
            
            // VIX Chart
            const vixCtx = document.getElementById('vixChart').getContext('2d');
            new Chart(vixCtx, {
                type: 'line',
                data: {
                    labels: timeLabels,
                    datasets: [{
                        label: 'VIX',
                        data: [20.5, 21.2, 20.8, 21.5, 22.1, 21.8, 21.3, 21.9, 21.6, 21.4],
                        borderColor: '#dc2626',
                        backgroundColor: 'rgba(220, 38, 38, 0.1)',
                        fill: false,
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: false }
                    }
                }
            });
            
            // USD/EUR Chart
            const usdeurCtx = document.getElementById('usdeurChart').getContext('2d');
            new Chart(usdeurCtx, {
                type: 'line',
                data: {
                    labels: timeLabels,
                    datasets: [{
                        label: 'USD/EUR',
                        data: [1.0850, 1.0865, 1.0840, 1.0875, 1.0890, 1.0860, 1.0855, 1.0870, 1.0885, 1.0875],
                        borderColor: '#16a34a',
                        backgroundColor: 'rgba(22, 163, 74, 0.1)',
                        fill: false,
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: false }
                    }
                }
            });
        });
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)
