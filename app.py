from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import os

app = Flask(__name__)
CORS(app)

# Load MongoDB connection from environment variable
mongo_uri = os.getenv("MONGO_URI")
if not mongo_uri:
    raise ValueError("MONGO_URI is not set in environment variables!")

# Connect to MongoDB Atlas
client = MongoClient(mongo_uri)
db = client["invmanage"]   # use your database name
customers_collection = db["customers"]

# ---------------- ROUTES ---------------- #

@app.route("/")
def home():
    return jsonify({"message": "Flask + MongoDB backend is running!"})

# Add customer
@app.route("/customers", methods=["POST"])
def add_customer():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    result = customers_collection.insert_one(data)
    return jsonify({"message": "Customer added", "id": str(result.inserted_id)}), 201

# Get all customers
@app.route("/customers", methods=["GET"])
def get_customers():
    customers = list(customers_collection.find({}, {"_id": 0}))
    return jsonify(customers), 200

# Update customer
@app.route("/customers/<string:name>", methods=["PUT"])
def update_customer(name):
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    result = customers_collection.update_one({"name": name}, {"$set": data})
    if result.matched_count == 0:
        return jsonify({"error": "Customer not found"}), 404
    
    return jsonify({"message": "Customer updated"}), 200

# Delete customer
@app.route("/customers/<string:name>", methods=["DELETE"])
def delete_customer(name):
    result = customers_collection.delete_one({"name": name})
    if result.deleted_count == 0:
        return jsonify({"error": "Customer not found"}), 404
    
    return jsonify({"message": "Customer deleted"}), 200


# ---------------- RUN ---------------- #
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
