from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from bson.objectid import ObjectId
import os

# Flask app
app = Flask(__name__)
CORS(app, origins=["https://invmanage-frontend.vercel.app"], methods=["GET", "POST", "PUT", "DELETE"])

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
customers_collection = db["customers"]
suppliers_collection = db["suppliers"]
orders_collection = db["orders"]

# ===========================
# Seed Admin User
# ===========================
if not users_collection.find_one({"username": "admin"}):
    users_collection.insert_one({
        "username": "admin",
        "password": "password123"
    })
    print("✅ Admin user created: admin / password123")
else:
    print("ℹ️ Admin user already exists")

# ===========================
# AUTH ROUTES
# ===========================
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    if users_collection.find_one({"username": username}):
        return jsonify({"error": "User already exists"}), 400

    users_collection.insert_one({"username": username, "password": password})
    return jsonify({"message": "User registered successfully"}), 201

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    user = users_collection.find_one({"username": username, "password": password})
    if not user:
        return jsonify({"error": "Invalid username or password"}), 401

    return jsonify({"message": "Login successful"}), 200

# ===========================
# PRODUCT ROUTES (CRUD with _id)
# ===========================
@app.route("/api/products", methods=["GET"])
def get_products():
    products = []
    for p in products_collection.find({}):
        p["_id"] = str(p["_id"])
        if "reorderThreshold" not in p:
            p["reorderThreshold"] = ''
        products.append(p)
    return jsonify(products), 200

@app.route("/api/products", methods=["POST"])
def add_product():
    data = request.get_json()
    name = data.get("name")
    price = data.get("price")
    quantity = data.get("quantity")
    reorder_threshold = data.get("reorderThreshold")

    if not name or price is None or quantity is None:
        return jsonify({"error": "Name, price, and quantity required"}), 400

    product = {
        "name": name,
        "price": price,
        "quantity": quantity,
        "reorderThreshold": reorder_threshold
    }
    products_collection.insert_one(product)
    return jsonify({"message": "Product added successfully"}), 201

@app.route("/api/products/<string:product_id>", methods=["PUT"])
def update_product(product_id):
    data = request.get_json()
    updated_data = {}

    if "price" in data:
        updated_data["price"] = data["price"]
    if "quantity" in data:
        updated_data["quantity"] = data["quantity"]
    if "reorderThreshold" in data:
        updated_data["reorderThreshold"] = data["reorderThreshold"]

    if not updated_data:
        return jsonify({"error": "No fields to update"}), 400

    try:
        result = products_collection.update_one({"_id": ObjectId(product_id)}, {"$set": updated_data})
        if result.matched_count == 0:
            return jsonify({"error": "Product not found"}), 404
        updated_product = products_collection.find_one({"_id": ObjectId(product_id)})
        updated_product["_id"] = str(updated_product["_id"])
        return jsonify(updated_product), 200
    except Exception as e:
        app.logger.error(f"Error updating product: {e}")
        return jsonify({"error": "Failed to update product"}), 500

@app.route("/api/products/<string:product_id>", methods=["DELETE"])
def delete_product(product_id):
    try:
        result = products_collection.delete_one({"_id": ObjectId(product_id)})
        if result.deleted_count == 0:
            return jsonify({"error": "Product not found"}), 404
        return jsonify({"message": "Product deleted successfully"}), 200
    except Exception as e:
        app.logger.error(f"Error deleting product: {e}")
        return jsonify({"error": "Failed to delete product"}), 500

# ===========================
# CUSTOMER ROUTES
# ===========================
@app.route("/api/customers", methods=["GET"])
def get_customers():
    customers = list(customers_collection.find({}, {"_id": 0}))
    return jsonify(customers), 200

@app.route("/api/customers", methods=["POST"])
def add_customer():
    data = request.get_json()
    name = data.get("name")
    contact = data.get("contact")
    address = data.get("address")

    if not name or not contact or not address:
        return jsonify({"error": "Name, contact, and address required"}), 400

    customer = {"name": name, "contact": contact, "address": address}
    customers_collection.insert_one(customer)
    return jsonify({"message": "Customer added successfully"}), 201

# ===========================
# SUPPLIER ROUTES
# ===========================
@app.route("/api/suppliers", methods=["GET"])
def get_suppliers():
    suppliers = list(suppliers_collection.find({}, {"_id": 0}))
    return jsonify(suppliers), 200

@app.route("/api/suppliers", methods=["POST"])
def add_supplier():
    data = request.get_json()
    name = data.get("name")
    contact = data.get("contact")
    address = data.get("address")

    if not name or not contact or not address:
        return jsonify({"error": "Name, contact, and address required"}), 400

    supplier = {"name": name, "contact": contact, "address": address}
    suppliers_collection.insert_one(supplier)
    return jsonify({"message": "Supplier added successfully"}), 201

# ===========================
# ORDERS ROUTES
# ===========================
@app.route("/api/orders", methods=["GET"])
def get_orders():
    orders = list(orders_collection.find({}, {"_id": 0}))
    return jsonify(orders), 200

@app.route("/api/orders", methods=["POST"])
def add_order():
    data = request.get_json()
    customer_name = data.get("customer_name")
    product_name = data.get("product_name")
    quantity = data.get("quantity")
    order_date = data.get("order_date")

    if not customer_name or not product_name or quantity is None:
        return jsonify({"error": "customer_name, product_name and quantity required"}), 400

    order = {
        "customer_name": customer_name,
        "product_name": product_name,
        "quantity": quantity,
        "order_date": order_date
    }
    orders_collection.insert_one(order)
    return jsonify({"message": "Order added successfully"}), 201

# ===========================
# HEALTH CHECK
# ===========================
@app.route("/api/ping", methods=["GET"])
def ping():
    return jsonify({"status": "ok"}), 200

# ===========================
# MAIN ENTRY
# ===========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
