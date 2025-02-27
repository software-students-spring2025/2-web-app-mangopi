import os
import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import pymongo
from bson.objectid import ObjectId

load_dotenv()

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data["_id"])
        self.name = user_data.get("name", "")  # Use get with default value
        self.email = user_data.get("email", "")  # Use get with default value
        
    @staticmethod
    def get(user_id, db):
        try:
            user_data = db.users.find_one({"_id": ObjectId(user_id)})
            if user_data:
                return User(user_data)
        except Exception as e:
            print(f"Error retrieving user: {e}")
        return None

def create_app():
    """
    Create and configure the Flask application with MongoDB.
    """
    app = Flask(__name__)
    app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")

    # Setup Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "login"
    
    MONGO_URI = os.getenv("MONGO_URI")
    MONGO_DBNAME = os.getenv("MONGO_DBNAME")

    cxn = pymongo.MongoClient(MONGO_URI)
    db = cxn[MONGO_DBNAME]
    logs_collection = db["test_logs"] # TODO: Configure correct db for add_log
    users_collection = db["users"]  # Collection for user data

    try:
        cxn.admin.command("ping")
        print(" * Connected to MongoDB!")
    except Exception as e:
        print(" * MongoDB connection error:", e)
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.get(user_id, db)
    
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email")
            password = request.form.get("password")
            
            # Validate inputs
            if not all([email, password]):
                flash("Email and password are required")
                return render_template("login.html")
                
            try:
                user_data = users_collection.find_one({"email": email})
                
                if user_data and "password" in user_data and check_password_hash(user_data["password"], password):
                    user = User(user_data)
                    login_user(user)
                    return redirect(url_for("home"))
                else:
                    flash("Invalid email or password")
            except Exception as e:
                print(f"Error during login: {e}")
                flash("An error occurred during login")
        
        return render_template("login.html")
    
    @app.route("/logout")
    def logout():
        logout_user()
        return redirect(url_for("login"))
    
    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            name = request.form.get("name")
            email = request.form.get("email")
            password = request.form.get("password")
            
            # Validate inputs
            if not all([name, email, password]):
                flash("All fields are required")
                return render_template("signup.html")
                
            # Check if user already exists
            if users_collection.find_one({"email": email}):
                flash("Email already exists")
                return render_template("signup.html")
            
            # Create new user
            try:
                hashed_password = generate_password_hash(password)
                new_user = {
                    "name": name,
                    "email": email,
                    "password": hashed_password,
                    "created_at": datetime.datetime.utcnow()
                }
                
                result = users_collection.insert_one(new_user)
                
                # Automatically log in the new user
                user_data = users_collection.find_one({"_id": result.inserted_id})
                if user_data:
                    user = User(user_data)
                    login_user(user)
                    return redirect(url_for("accountsetting"))
                else:
                    flash("Error creating account")
            except Exception as e:
                print(f"Error creating user: {e}")
                flash("An error occurred during signup")
            
        return render_template("signup.html")
    
    @app.route("/accountsetting")
    @login_required
    def accountsetting():
        return render_template("accountsetting.html")

    @app.route("/home")
    @login_required
    def home():
        return render_template("home.html")

    @app.route("/measurements")
    @login_required
    def measurements():
        return render_template("measurements.html")

    @app.route("/community")
    @login_required
    def community():
        return render_template("community.html")

    @app.route("/profile")
    @login_required
    def profile():
        return render_template("profile.html")

    @app.route("/add_log", methods=["GET", "POST"])
    @login_required
    def add_log():
        if request.method == "POST":
            body_weight = request.form.get("body_weight")
            body_fat = request.form.get("body_fat")
            waist  = request.form.get("waist")
            shoulder = request.form.get("shoulder")
            chest = request.form.get("chest")
            abdomen = request.form.get("abdomen")
            hip = request.form.get("hip")
            left_thigh = request.form.get("left_thigh")
            right_thigh = request.form.get("right_thigh")
            
            # Create a new log with user ID
            doc = {
                "user_id": current_user.id,
                "body_weight": body_weight,
                "body_fat": body_fat,
                "waist": waist,
                "shoulder": shoulder,
                "chest": chest,
                "abdomen": abdomen,
                "hip": hip,
                "left_thigh": left_thigh,
                "right_thigh": right_thigh,
                "created_at": datetime.datetime.utcnow()
            }
            logs_collection.insert_one(doc)
            
            # Redirect to measurements after saving
            return redirect(url_for("measurements"))
        
        return render_template("add_log.html")
    
    @app.route("/edit_log/<log_id>", methods=["GET", "POST"])
    @login_required
    def edit_log(log_id):
        log = logs_collection.find_one({"_id": ObjectId(log_id), "user_id": current_user.id})

        if not log:
            flash("Log not found")
            return redirect(url_for("measurements"))
        
        if request.method == "POST":
            body_weight = request.form.get("body_weight")
            body_fat = request.form.get("body_fat")
            waist  = request.form.get("waist")
            shoulder = request.form.get("shoulder")
            chest = request.form.get("chest")
            abdomen = request.form.get("abdomen")
            hip = request.form.get("hip")
            left_thigh = request.form.get("left_thigh")
            right_thigh = request.form.get("right_thigh")

            update_fields = {
                "body_weight": body_weight,
                "body_fat": body_fat,
                "waist": waist,
                "shoulder": shoulder,
                "chest": chest,
                "abdomen": abdomen,
                "hip": hip,
                "left_thigh": left_thigh,
                "right_thigh": right_thigh,
                "updated_at": datetime.datetime.utcnow()
            }

            logs_collection.update_one({"_id": ObjectId(log_id)}, {"$set": update_fields})

            return redirect(url_for("measurements"))
        
        return render_template("edit_log.html", log=log)

    @app.route("/delete_log/<log_id>", methods=["GET", "POST"])
    @login_required
    def delete_log(log_id):
        logs_collection.delete_one({"_id": ObjectId(log_id), "user_id": current_user.id})
        return redirect(url_for("measurements"))

    @app.route("/")
    def index():
        return redirect(url_for("login"))

    return app

if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("FLASK_PORT", "5001"))
    print(f"Starting app on port {port}...")
    app.run(host="0.0.0.0", port=port)