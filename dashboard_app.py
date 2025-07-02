from flask import Flask, render_template
from dashboard.routes import dashboard_bp

app = Flask(__name__)
app.register_blueprint(dashboard_bp, url_prefix="/")

@app.route("/")
def home():
    return render_template("dashboard.html")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5050)
