from flask import Flask, request, jsonify
from pymongo import MongoClient
from flask_cors import CORS
from bson.objectid import ObjectId
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)

# ✅ MongoDB Connection
app.config["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/inventorydb")
mongo = PyMongo(app)

# Collections
users_collection = mongo.db.users
products_collection = mongo.db.products
customers_collection = mongo.db.customers
suppliers_collection = mongo.db.suppliers
orders_collection = mongo.db.orders


# ✅ Universal Serializer for ObjectId & datetime
def serialize_doc(doc):
    """Recursively convert ObjectId and datetime so Flask can jsonify"""
    if isinstance(doc, list):
        return [serialize_doc(d) for d in doc]
    if isinstance(doc, dict):
        new_doc = {}
        for k, v in doc.items():
            if isinstance(v, ObjectId):
                new_doc[k] = str(v)
            elif isinstance(v, datetime):
                new_doc[k] = v.isoformat()
            elif isinstance(v, dict):
                new_doc[k] = serialize_doc(v)
            elif isinstance(v, list):
                new_doc[k] = [serialize_doc(i) for i in v]
            else:
                new_doc[k] = v
        return new_doc
    return doc


# ==========================
# ✅ Authentication
# ==========================
@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    user = users_collection.find_one({"username": username, "password": password})
    if user:
        return jsonify({"success": True, "username": username}), 200
    return jsonify({"success": False, "message": "Invalid username or password"}), 401


# ==========================
# ✅ Products
# ==========================
@app.route("/api/products", methods=["GET"])
def get_products():
    products = list(products_collection.find())
    return jsonify(serialize_doc(products)), 200


@app.route("/api/products", methods=["POST"])
def add_product():
    data = request.json
    result = products_collection.insert_one(data)
    return jsonify({"success": True, "id": str(result.inserted_id)}), 201


# ==========================
# ✅ Customers
# ==========================
@app.route("/api/customers", methods=["GET"])
def get_customers():
    customers = list(customers_collection.find())
    return jsonify(serialize_doc(customers)), 200


@app.route("/api/customers", methods=["POST"])
def add_customer():
    data = request.json
    result = customers_collection.insert_one(data)
    return jsonify({"success": True, "id": str(result.inserted_id)}), 201


# ==========================
# ✅ Suppliers
# ==========================
@app.route("/api/suppliers", methods=["GET"])
def get_suppliers():
    suppliers = list(suppliers_collection.find())
    return jsonify(serialize_doc(suppliers)), 200


@app.route("/api/suppliers", methods=["POST"])
def add_supplier():
    data = request.json
    result = suppliers_collection.insert_one(data)
    return jsonify({"success": True, "id": str(result.inserted_id)}), 201


# ==========================
# ✅ Orders
# ==========================
@app.route("/api/orders", methods=["GET"])
def get_orders():
    orders = list(orders_collection.find())
    enriched_orders = []
    for order in orders:
        customer = customers_collection.find_one({"_id": order.get("customer_id")})
        order["customer_name"] = customer["name"] if customer else "Unknown"
        enriched_orders.append(order)
    return jsonify(serialize_doc(enriched_orders)), 200


@app.route("/api/orders", methods=["POST"])
def add_order():
    data = request.json
    data["date"] = datetime.utcnow()
    result = orders_collection.insert_one(data)
    return jsonify({"success": True, "id": str(result.inserted_id)}), 201


# ==========================
# ✅ Dashboard
# ==========================
@app.route("/api/dashboard", methods=["GET"])
def dashboard():
    product_count = products_collection.count_documents({})
    customer_count = customers_collection.count_documents({})
    supplier_count = suppliers_collection.count_documents({})
    order_count = orders_collection.count_documents({})

    stats = {
        "products": product_count,
        "customers": customer_count,
        "suppliers": supplier_count,
        "orders": order_count,
    }
    return jsonify(serialize_doc(stats)), 200


# ==========================
# ✅ AI Insights (Mock Example)
# ==========================
@app.route("/api/ai-insights", methods=["GET"])
def ai_insights():
    insights = {
        "top_selling": "Laptop",
        "low_stock": "Printer Ink",
        "recommendation": "Restock USB Cables soon",
    }
    return jsonify(serialize_doc(insights)), 200


# ==========================
# ✅ Health Check
# ==========================
@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Backend is running with MongoDB!"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
