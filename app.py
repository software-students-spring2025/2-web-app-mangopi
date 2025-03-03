import os
import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import pymongo
from bson.objectid import ObjectId
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import plotly.io as pio
import openai 

load_dotenv(override=True)
openai.api_key = os.getenv("OPENAI_API_KEY")

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
    posts_collection = db["posts"]

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

    # Generate AI-driven feedback for users' fitness progress
    def generate_fitness_feedback(logs, user_goal):
        if not logs or len(logs) < 2:
            return "You haven't recorded enough data yet. Keep tracking your progress!"
        
        # Extract measurement trends
        first_log = logs[0]
        latest_log = logs[-1]
        changes = {}

        measurement_fields = [
            "body_weight", "body_fat", "waist", "shoulder", "chest",
            "abdomen", "hip", "left_thigh", "right_thigh"
        ]

        # Analyze trends
        for field in measurement_fields:
            try:
                initial = float(first_log.get(field, 0))
                latest = float(latest_log.get(field, 0))
                change = latest - initial
                changes[field] = change
            except ValueError:
                continue
    
        # AI prompt for fitness insights
        trend_summary = []
        for field, change in changes.items():
            trend_summary.append(f"{field.replace('_', ' ').title()} changed by {change:.1f} cm/kg.")

        trend_text = " ".join(trend_summary)

        # Personalized the prompt based on the users' goal
        goal_text = (
            "weight loss" if user_goal == "lose-weight" 
            else "muscle building and body shaping"
        )

        prompt = f"""
        You are a professional fitness trainer. The user has a goal of {goal_text}.
        Here are their progress changes:
        {trend_text}
        Provide personalized feedback based on their progress, including recommendations for diet and exercise.
        """

        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a fitness expert providing personalized advice."},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error generating AI feedback: {e}")
            return "Could not generate AI insights at this time."
        

    @app.route("/home")
    @login_required
    def home():
        # Query logs for the current user sorted in ascending order by creation time.
        logs = list(logs_collection.find({"user_id": "12345"}).sort("created_at", 1)) # Replace current_user.id with 12345 for data visualization
        user_data = users_collection.find_one({"_id": ObjectId(current_user.id)})
        user_goal = user_data.get("goal", "lose-weight")  # Default to weight loss if goal is missing

        # Generate AI-based feedback
        ai_feedback = generate_fitness_feedback(logs, user_goal)

        if logs:

            timestamps = [log.get("created_at") for log in logs if "created_at" in log and log["created_at"] is not None]
        
            # All keys to display
            measurement_keys = [
                "body_weight", "body_fat", "waist", 
                "shoulder", "chest", "abdomen", 
                "hip", "left_thigh", "right_thigh"
            ]
            
            measurements = {
                key: [float(log[key]) for log in logs if key in log and log[key] is not None and isinstance(log[key], (int, float))]
                for key in measurement_keys
            }
            
            num_measurements = sum(1 for key in measurement_keys if measurements[key])
            
            if num_measurements > 0:
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
        else:
            plot_html = "<p>You haven't added your body information yet. Start Now!<p>"
            
        return render_template("home.html", plot_html=plot_html, ai_feedback = ai_feedback)
        

    @app.route("/measurements")
    @login_required
    def measurements():
        logs = logs_collection.find({"user_id": current_user.id}).sort("created_at", -1)
        return render_template("measurements.html", logs=logs)
    
    @app.route("/community")
    @login_required
    def community():
        posts = list(posts_collection.find().sort("created_at", -1))

        for post in posts:
            if isinstance(post.get("created_at"), str):
                try:
                    post["created_at"] = datetime.datetime.fromisoformat(post["created_at"])
                except ValueError:
                    post["created_at"] = datetime.datetime.utcnow()  # 兜底

            post["created_at"] = post["created_at"].strftime('%Y-%m-%d %H:%M')

        return render_template("community.html", posts=posts)
    
    @app.route("/like_post/<post_id>", methods=["POST"])
    @login_required
    def like_post(post_id):
        post = posts_collection.find_one({"_id": ObjectId(post_id)})

        if not post:
            return jsonify({"error": "Post not found"}), 404

        # 读取当前点赞数，如果没有，则初始化
        current_likes = post.get("likes", 0)
        user_id = str(current_user.id)

        # 如果帖子已经有 likes_users 记录，检查用户是否已经点赞
        if "likes_users" not in post:
            post["likes_users"] = []

        if user_id in post["likes_users"]:
            post["likes_users"].remove(user_id)
            new_likes = max(0, current_likes - 1)
        else:
            post["likes_users"].append(user_id)
            new_likes = current_likes + 1

        posts_collection.update_one(
            {"_id": ObjectId(post_id)},
            {"$set": {"likes": new_likes, "likes_users": post["likes_users"]}}
        )

        return jsonify({"likes": new_likes, "liked": user_id in post["likes_users"]})



    
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
    
    @app.route("/add_post", methods=["GET", "POST"])
    @login_required
    def add_post():
        if request.method == "POST":
            content = request.form.get("content")
            privacy = request.form.get("privacy")
            tags = request.form.getlist("tag")

            # 确保内容和可见性
            if not content or not privacy:
                flash("Post content and visibility are required!", "danger")
                return redirect(url_for("add_post"))

            post = {
                "user_id": ObjectId(current_user.id),
                "username": current_user.name,
                "content": content,
                "visibility": privacy,
                "tags": tags,
                "created_at": datetime.datetime.utcnow()
            }

            # 插入数据库
            posts_collection.insert_one(post)

            flash("Post added successfully!", "success")
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
    
    @app.route("/edit_post/<post_id>", methods=["GET", "POST"])
    @login_required
    def edit_post(post_id):
        """ Load or update the edit post page with the current post details. """
        post = posts_collection.find_one({"_id": ObjectId(post_id)})

        if not post:
            flash("Post not found!", "danger")
            return redirect(url_for("postlist"))

        if request.method == "POST":
            content = request.form.get("content")
            privacy = request.form.get("privacy")
            tags = request.form.getlist("tag")  # Handle multiple tags

            # Update post fields
            update_fields = {
                "content": content,
                "privacy": privacy,
                "tags": tags,
                "updated_at": datetime.utcnow(),
            }

            posts_collection.update_one({"_id": ObjectId(post_id)}, {"$set": update_fields})
            flash("Post updated successfully!", "success")
            return redirect(url_for("postlist"))

        return render_template("edit_post.html", post=post)


    
    # Delete in MongoDB
    @app.route("/delete_post/<post_id>", methods=["POST"])
    @login_required
    def delete_post(post_id):
        post = posts_collection.find_one({"_id": ObjectId(post_id)})

        if not post:
            flash("Post not found!", "danger")
            return redirect(url_for("postlist"))

        posts_collection.delete_one({"_id": ObjectId(post_id)})
        flash("Post deleted successfully!", "success")

        return redirect(url_for("postlist"))


    @app.route("/")
    def index():
        return redirect(url_for("login"))

    return app

if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("FLASK_PORT", "5001"))
    print(f"Starting app on port {port}...")
    app.run(host="0.0.0.0", port=port)
