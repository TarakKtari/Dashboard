
from flask import Blueprint, render_template, redirect, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import User
from functools import wraps
import eikon as ek
import pandas as pd

# Blueprint setup

dashboard_bp = Blueprint('dashboard_bp', __name__, template_folder='templates', static_folder='static')

def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user or not user.is_admin:
            return redirect(url_for('user_bp.get_open_positions'))  # or a 403 page
        return fn(*args, **kwargs)
    return wrapper

@dashboard_bp.route('/dashboard')
@admin_required
def dashboard():
    vix_data = get_vix_data()
    dxy_data = get_dxy_data()
    return render_template('dashboard.html', vix_data=vix_data, dxy_data=dxy_data)


# Set your Eikon API key (replace with your actual key or use env variable)
ek.set_app_key("20af0572a6364fe8abf9a35cdd16bd367057564a")

def get_vix_data():
    vix_df = ek.get_timeseries(".VIX", interval="minute", count=36)
    if vix_df is None or vix_df.empty:
        return []
    vix_df.index = pd.to_datetime(vix_df.index)
    vix_5m = vix_df.resample("5T").agg({
        "OPEN": "first",
        "HIGH": "max",
        "LOW": "min",
        "CLOSE": "last"
    }).dropna().reset_index()
    # Rename columns for frontend compatibility
    vix_5m = vix_5m.rename(columns={"index": "Datetime", "OPEN": "Open", "HIGH": "High", "LOW": "Low", "CLOSE": "Close"})
    return vix_5m.to_dict(orient="records")

def get_dxy_data():
    dxy_df = ek.get_timeseries(".DXY", interval="minute", count=36)
    if dxy_df is None or dxy_df.empty:
        return []
    dxy_df.index = pd.to_datetime(dxy_df.index)
    dxy_5m = dxy_df.resample("5T").agg({
        "OPEN": "first",
        "HIGH": "max",
        "LOW": "min",
        "CLOSE": "last"
    }).dropna().reset_index()
    dxy_5m = dxy_5m.rename(columns={"index": "Datetime", "OPEN": "Open", "HIGH": "High", "LOW": "Low", "CLOSE": "Close"})
    return dxy_5m.to_dict(orient="records")

