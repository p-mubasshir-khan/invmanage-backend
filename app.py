from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
import os

# Flask app
app = Flask(__name__)
CORS(app)

# Secret Key
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "fallbacksecret")

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise Exception("❌ MONGO_URI not set in environment variables")

client = MongoClient(MONGO_URI)
db = client["invmanage"]

# Collections
users_collection = db["users"]
products_collection = db["products"]

# ===========================
# Seed Admin User
# ===========================
if not users_collection.find_one({"username": "admin"}):
    hashed_pw = generate_password_hash("password123")
    users_collection.insert_one({
        "username": "admin",
        "password": hashed_pw
    })
    print("✅ Admin user created: admin / password123")
else:
    print("ℹ️ Admin user already exists")


# ===========================
# AUTH ROUTES
# ===========================
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    if users_collection.find_one({"username": username}):
        return jsonify({"error": "User already exists"}), 400

    hashed_pw = generate_password_hash(password)
    users_collection.insert_one({"username": username, "password": hashed_pw})
    return jsonify({"message": "User registered successfully"}), 201


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    user = users_collection.find_one({"username": username})
    if not user:
        return jsonify({"error": "Invalid username or password"}), 401

    if not check_password_hash(user["password"], password):
        return jsonify({"error": "Invalid username or password"}), 401

    return jsonify({"message": "Login successful"}), 200


# ===========================
# PRODUCT ROUTES (CRUD)
# ===========================
@app.route("/products", methods=["GET"])
def get_products():
    products = list(products_collection.find({}, {"_id": 0}))
    return jsonify(products), 200


@app.route("/products", methods=["POST"])
def add_product():
    data = request.get_json()
    name = data.get("name")
    price = data.get("price")
    quantity = data.get("quantity")

    if not name or price is None or quantity is None:
        return jsonify({"error": "Name, price, and quantity required"}), 400

    product = {"name": name, "price": price, "quantity": quantity}
    products_collection.insert_one(product)
    return jsonify({"message": "Product added successfully"}), 201


@app.route("/products/<string:name>", methods=["PUT"])
def update_product(name):
    data = request.get_json()
    updated_data = {}

    if "price" in data:
        updated_data["price"] = data["price"]
    if "quantity" in data:
        updated_data["quantity"] = data["quantity"]

    if not updated_data:
        return jsonify({"error": "No fields to update"}), 400

    result = products_collection.update_one({"name": name}, {"$set": updated_data})

    if result.matched_count == 0:
        return jsonify({"error": "Product not found"}), 404

    return jsonify({"message": "Product updated successfully"}), 200


@app.route("/products/<string:name>", methods=["DELETE"])
def delete_product(name):
    result = products_collection.delete_one({"name": name})

    if result.deleted_count == 0:
        return jsonify({"error": "Product not found"}), 404

    return jsonify({"message": "Product deleted successfully"}), 200


# ===========================
# MAIN ENTRY
# ===========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
