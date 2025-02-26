from flask import Flask, render_template, request, redirect, url_for, session
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt

app = Flask(__name__)
app.secret_key = "mySecretKey"

# MongoDP Atlas Connection
app.config["MONGO_URI"] = "mongodb+srv://sg7510:Sdecode112358s!@cluster0.dwknr.mongodb.net/zifan_test"
mongo = PyMongo(app)
bcrypt = Bcrypt(app)

# User Registrattion
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form['email']
        password = request.form['password']

        # Check if user exists
        userExist = mongo.db.users.find_one({"email": email})
        if userExist:
            return "Email already used!"
        
        # Set password and store the user
        hashed_pw = bcrypt.generate_password_hash(password).decode("utf-8")
        mongo.db.users.insert_one({"email": email, "password": hashed_pw})
        return redirect(url_for("login"))

# User Login
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = mongo.db.users.find_one({"email": email})
        if user and bcrypt.check_password_hash(user["password"], password):
            session["email"] = email
            return "Welcome" + email 
        else:
            return "Invalid email or password. Try again."

    return render_template("welcome.html")

# Logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)