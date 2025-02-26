import os
import datetime
from flask import Flask, render_template, request, redirect, url_for
from dotenv import load_dotenv
import pymongo

 
load_dotenv()

def create_app():
    """
    Create and configure the Flask application with MongoDB.
    """
    app = Flask(__name__)

    MONGO_URI = os.getenv("MONGO_URI")
    MONGO_DBNAME = os.getenv("MONGO_DBNAME")

    cxn = pymongo.MongoClient(MONGO_URI)
    db = cxn[MONGO_DBNAME]
    logs_collection = db["test_logs"]  

    try:
        cxn.admin.command("ping")
        print(" * Connected to MongoDB!")
    except Exception as e:
        print(" * MongoDB connection error:", e)

    @app.route("/home")
    def home():
        return render_template("home.html")

    @app.route("/measurements")
    def measurements():
        return render_template("measurements.html")

    @app.route("/community")
    def community():
        return render_template("community.html")

    @app.route("/profile")
    def profile():
        return render_template("profile.html")

    @app.route("/add_log", methods=["GET", "POST"])
    def add_log():
        """
        Handles log addition:
        - GET request: Shows the Add Log form
        - POST request: Saves form data to MongoDB and redirects to measurements
        """
        if request.method == "POST":
            body_weight = request.form.get("body_weight")
            body_fat = request.form.get("body_fat")
            
            # Create a new log
            doc = {
                "body_weight": body_weight,
                "body_fat": body_fat,
                "created_at": datetime.datetime.utcnow()
            }
            logs_collection.insert_one(doc)
            
            # Redirect to measurements after saving
            return redirect(url_for("measurements"))
        
        return render_template("add_log.html")

    @app.route("/")
    def index():
        return redirect(url_for("home"))

    return app

if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("FLASK_PORT", "5001"))
    print(f"Starting app on port {port}...")
    app.run(host="0.0.0.0", port=port)