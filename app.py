import os
import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import pymongo
from bson.objectid import ObjectId
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import plotly.io as pio

load_dotenv(override=True)

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
    logs_collection = db["demo_logs_test"] # TODO: Configure correct db for add_log
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
    
    @app.route("/accountsetting", methods=["GET", "POST"])
    @login_required
    def accountsetting():
        user_data = users_collection.find_one({"_id": ObjectId(current_user.id)})

        if request.method == "POST":
            gender = request.form.get("gender")
            dob = request.form.get("dob")
            goal = request.form.get("goal")

            # update the preferences
            update_fields = {
                "gender": gender,
                "dob": dob,
                "goal": goal,
            }

            users_collection.update_one({"_id": ObjectId(current_user.id)}, {"$set": update_fields})
            return redirect(url_for("login"))
        
        flash("No Error Message (Debug)")
        return render_template("accountsetting.html", user = user_data)

    @app.route("/home")
    @login_required
    def home():
        # Query logs for the current user sorted in ascending order by creation time.
        logs = list(logs_collection.find({"user_id": "12345"}).sort("created_at", 1)) # Replace current_user.id with 12345 for data visualization
        if logs:

            timestamps = [log["created_at"] for log in logs]
        
            # All keys to display
            measurement_keys = [
                "body_weight", "body_fat", "waist", 
                "shoulder", "chest", "abdomen", 
                "hip", "left_thigh", "right_thigh"
            ]
            
            #TODO: Add AI Analysis of the data trend and advice heres
            

            measurements = {}
            for key in measurement_keys:
                measurements[key] = [float(log[key]) for log in logs if key in log and log[key] is not None]
            
            num_measurements = len(measurement_keys)
            fig = make_subplots(
                rows=num_measurements, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.03,
                subplot_titles=[key.replace("_", " ").title() for key in measurement_keys]
            )
            
            row = 1
            for key in measurement_keys:
                if measurements[key]:
                    fig.add_trace(
                        go.Scatter(
                            x=timestamps, 
                            y=measurements[key],
                            mode="lines+markers",
                            name=key
                        ),
                        row=row, col=1
                    )
                row += 1
            
            fig.update_layout(
                height=250 * num_measurements,
                title_text="Trend Analysis: Your Measurements"
            )
        
            
            plot_html = pio.to_html(fig, full_html=False)
        else:
            plot_html = "<p>You haven't added your body information yet. Start Now!</p>"
            
        return render_template("home.html", plot_html=plot_html)

    @app.route("/measurements")
    @login_required
    def measurements():
        logs = logs_collection.find({"user_id": current_user.id}).sort("created_at", -1)
        return render_template("measurements.html", logs=logs)
    
    
    @app.route("/community")
    @login_required
    def community():
        # Get latest posts
        posts = db.posts.find().sort("created_at", -1)  
        friends = db.users.find({"_id": {"$ne": ObjectId(current_user.id)}})  

        return render_template("community.html", posts=posts, friends=friends)
    
    @app.route("/add_friend", methods=["GET", "POST"])
    @login_required
    def add_friend():
        if request.method == "POST":
            friend_email = request.form.get("email")
            if not friend_email:
                flash("Please enter a valid email", "danger")
                return redirect(url_for("add_friend"))

            friend = db.users.find_one({"email": friend_email})
            if not friend:
                flash("User not found!", "danger")
                return redirect(url_for("add_friend"))

            # 获取 friend ID
            friend_id = friend["_id"]
            user_id = ObjectId(current_user.id)

            # 检查是否已经是好友
            if db.users.find_one({"_id": user_id, "friends": friend_id}):
                flash("Friend already added!", "warning")
                return redirect(url_for("community"))

            # 添加好友
            db.users.update_one(
                {"_id": user_id},
                {"$addToSet": {"friends": friend_id}}
            )
            flash("Friend added successfully!", "success")
            return redirect(url_for("community"))

        return render_template("add_friend.html")


    
    @app.route("/friendlist")
    @login_required
    def friendlist():
        return render_template("friendlist.html")
    
    @app.route("/search")
    @login_required
    def search():
        return render_template("search.html")
    
    @app.route("/postlist")
    @login_required
    def postlist():
        return render_template("postlist.html")
    
    @app.route("/edit_post")
    @login_required
    def edit_post():
        return render_template("edit_post.html")
    
    @app.route("/add_post")
    @login_required
    def add_post():
        content = request.form.get("content")
        if content:
            post = {"user_id": current_user.id, "content": content, "created_at": datetime.datetime.utcnow()}
            db.posts.insert_one(post)
            flash("Post added!", "success")
            return redirect(url_for("community"))
        return render_template("add_post.html")

    @app.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        try:
            # Access the MongoDB collection properly
            # We need to use current_app to access the application context if db is stored there
            from flask import current_app
            
            # Fetch user data from the database
            user_data = db.users.find_one({"_id": ObjectId(current_user.id)})

            if request.method == "POST":
                gender = request.form.get("gender")
                dob = request.form.get("dob")
                goal = request.form.get("goal")

                # Allowing update the user's profile fields in MongoDB
                db.users.update_one({"_id": ObjectId(current_user.id)}, {"$set": {"gender": gender, "dob": dob, "goal": goal}})
                flash("Profile updated!", "success")

                # Redirect back to /profile with updated data
                return redirect(url_for("profile"))
            
            return render_template("profile.html", user=user_data)
                
        except Exception as e:
                print(f"Error in profile route: {e}")
        # Return a basic template without user data to avoid errors
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

            errors = validate_measurements(body_weight, body_fat, waist, shoulder, chest, abdomen, hip, left_thigh, right_thigh)
            if errors:
                for error in errors:
                    flash(error, "danger")
                return render_template("add_log.html") 
            
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
            flash("Log added.", "success")
            
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

            errors = validate_measurements(body_weight, body_fat, waist, shoulder, chest, abdomen, hip, left_thigh, right_thigh)
            if errors:
                for error in errors:
                    flash(error, "danger")
                return render_template("edit_log.html", log=log)  # Reload form with errors

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
    
    # Value validations for input measurements by users to ensure all the info given are reasonable
    def validate_measurements(body_weight, body_fat, waist, shoulder, chest, abdomen, hip, left_thigh, right_thigh):
        """Validate user input to ensure measurements are within reasonable ranges."""
        errors = []

        # Define realistic measurement ranges
        min_weight, max_weight = 30, 500  # kg
        min_fat, max_fat = 5, 60  # %
        min_cm, max_cm = 30, 200  # cm
        min_shoulder, max_shoulder = 25, 70  # cm (shoulder width)
    
        try:
            # Convert inputs to float for validation
            body_weight = float(body_weight)
            body_fat = float(body_fat)
            waist = float(waist)
            shoulder = float(shoulder)
            chest = float(chest)
            abdomen = float(abdomen)
            hip = float(hip)
            left_thigh = float(left_thigh)
            right_thigh = float(right_thigh)
        
            # Validate each measurement
            if not (min_weight <= body_weight <= max_weight):
                errors.append("Body weight must be between 30kg and 500kg.")
            if not (min_fat <= body_fat <= max_fat):
                errors.append("Body fat percentage must be between 5% and 60%.")
            if not (min_cm <= waist <= max_cm):
                errors.append("Waist measurement must be between 30cm and 200cm.")
            if not (min_shoulder <= shoulder <= max_shoulder):
                errors.append("Shoulder width must be between 25cm and 70cm.")
            if not (min_cm <= chest <= max_cm):
                errors.append("Chest measurement must be between 30cm and 200cm.")
            if not (min_cm <= abdomen <= max_cm):
                errors.append("Abdomen measurement must be between 30cm and 200cm.")
            if not (min_cm <= hip <= max_cm):
                errors.append("Hip measurement must be between 30cm and 200cm.")
            if not (min_cm <= left_thigh <= max_cm):
                errors.append("Left thigh measurement must be between 30cm and 200cm.")
            if not (min_cm <= right_thigh <= max_cm):
                errors.append("Right thigh measurement must be between 30cm and 200cm.")

        except ValueError:
            errors.append("Invalid measurement value.")

        return errors


    @app.route("/")
    def index():
        return redirect(url_for("login"))

    return app

if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("FLASK_PORT", "5001"))
    print(f"Starting app on port {port}...")
    app.run(host="0.0.0.0", port=port)