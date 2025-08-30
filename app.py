
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Flask app
app = Flask(__name__)

# CORS configuration - allow both development and production origins
CORS(app, origins=[
    "https://invmanage-frontend.vercel.app",
    "http://localhost:3000",
    "http://localhost:5000"
], methods=["GET", "POST", "PUT", "DELETE"])

# Secret Key
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "fallbacksecret")

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://khansrmap_db_user:khan_8415@cluster0.mciv3wh.mongodb.net/")
client = MongoClient(MONGO_URI)
db = client["invmanage"]

# Collections
products_collection = db.products
orders_collection = db.orders
customers_collection = db.customers
suppliers_collection = db.suppliers
order_customers_collection = db.order_customers

# Helper function to convert ObjectId to string
def serialize_id(obj):
    if isinstance(obj, dict):
        if '_id' in obj:
            obj['id'] = str(obj['_id'])
            del obj['_id']
        for key, value in obj.items():
            if isinstance(value, datetime):
                obj[key] = value.isoformat()
            elif isinstance(value, dict):
                serialize_id(value)
    return obj

# Helper function to safely convert string to ObjectId
def safe_object_id(id_value):
    try:
        if isinstance(id_value, str):
            return ObjectId(id_value)
        elif isinstance(id_value, int):
            # Handle case where frontend sends integer ID
            return ObjectId(str(id_value))
        return id_value
    except:
        return None

# Hardcoded admin credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "password123"

# Authentication
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        return jsonify({'success': True, 'message': 'Login successful'})
    else:
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

# Product routes
@app.route('/api/products', methods=['GET'])
def get_products():
    products = list(products_collection.find())
    return jsonify([serialize_id(p) for p in products])

@app.route('/api/products', methods=['POST'])
def create_product():
    data = request.get_json()
    product = {
        'name': data['name'],
        'quantity': int(data['quantity']),
        'price': float(data['price']),
        'reorder_threshold': int(data['reorder_threshold']),
        'created_at': datetime.utcnow()
    }
    result = products_collection.insert_one(product)
    product['_id'] = result.inserted_id
    return jsonify(serialize_id(product)), 201

@app.route('/api/products/<product_id>', methods=['PUT'])
def update_product(product_id):
    object_id = safe_object_id(product_id)
    if not object_id:
        return jsonify({'error': 'Invalid product ID'}), 400
    data = request.get_json()
    update_data = {
        'name': data['name'],
        'quantity': int(data['quantity']),
        'price': float(data['price']),
        'reorder_threshold': int(data['reorder_threshold'])
    }
    result = products_collection.update_one({'_id': object_id}, {'$set': update_data})
    if result.matched_count == 0:
        return jsonify({'error': 'Product not found'}), 404
    updated_product = products_collection.find_one({'_id': object_id})
    return jsonify(serialize_id(updated_product))

@app.route('/api/products/<product_id>', methods=['DELETE'])
def delete_product(product_id):
    object_id = safe_object_id(product_id)
    if not object_id:
        return jsonify({'error': 'Invalid product ID'}), 400
    result = products_collection.delete_one({'_id': object_id})
    if result.deleted_count == 0:
        return jsonify({'error': 'Product not found'}), 404
    return jsonify({'message': 'Product deleted successfully'})

# Order routes
@app.route('/api/orders', methods=['GET'])
def get_orders():
    orders = list(orders_collection.find().sort('created_at', -1))
    product_ids = [o['product_id'] for o in orders]
    products = {str(p['_id']): p for p in products_collection.find({'_id': {'$in': product_ids}})}
    order_ids = [o['_id'] for o in orders]
    customer_mappings = list(order_customers_collection.find({'order_id': {'$in': order_ids}}))
    customer_ids = [m['customer_id'] for m in customer_mappings]
    customers = {str(c['_id']): c for c in customers_collection.find({'_id': {'$in': customer_ids}})}
    order_to_customer = {str(m['order_id']): str(m['customer_id']) for m in customer_mappings}
    enriched_orders = []
    for order in orders:
        order_str_id = str(order['_id'])
        product = products.get(str(order['product_id']))
        customer_id = order_to_customer.get(order_str_id)
        customer = customers.get(customer_id) if customer_id else None
        enriched_orders.append({
            'id': order_str_id,
            '_id': order_str_id,
            'product_id': str(order['product_id']),
            'product_name': product['name'] if product else 'Unknown Product',
            'quantity': order['quantity'],
            'total_amount': order['total_amount'],
            'created_at': order['created_at'].isoformat(),
            'customer_id': customer_id,
            'customer_name': customer['name'] if customer else None
        })
    return jsonify(enriched_orders)

@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.get_json()
    product_id = safe_object_id(data.get('product_id'))
    if not product_id:
        return jsonify({'error': 'Invalid product ID'}), 400
    product = products_collection.find_one({'_id': product_id})
    if not product:
        return jsonify({'error': 'Product not found'}), 404

    order_quantity = int(data['quantity'])
    if product['quantity'] < order_quantity:
        return jsonify({'error': 'Insufficient stock'}), 400

    total_amount = product['price'] * order_quantity
    order = {
        'product_id': product_id,
        'quantity': order_quantity,
        'total_amount': total_amount,
        'created_at': datetime.utcnow()
    }
    result = orders_collection.insert_one(order)
    order['_id'] = result.inserted_id

    # Decrement stock
    products_collection.update_one({'_id': product_id}, {'$inc': {'quantity': -order_quantity}})

    # Optional customer link
    customer_id_str = data.get('customer_id')
    customer = None
    if customer_id_str:
        customer_id = safe_object_id(customer_id_str)
        if customer_id:
            customer = customers_collection.find_one({'_id': customer_id})
            if customer:
                order_customers_collection.insert_one({
                    'order_id': order['_id'],
                    'customer_id': customer_id,
                    'created_at': datetime.utcnow()
                })

    # Enriched response
    resp = serialize_id(order)
    resp['product_name'] = product['name']
    if customer:
        resp['customer_id'] = customer_id_str
        resp['customer_name'] = customer['name']
    return jsonify(resp), 201

@app.route('/api/orders/<order_id>', methods=['DELETE'])
def delete_order(order_id):
    object_id = safe_object_id(order_id)
    if not object_id:
        return jsonify({'error': 'Invalid order ID'}), 400
    order = orders_collection.find_one({'_id': object_id})
    if not order:
        return jsonify({'error': 'Order not found'}), 404

    # Restore product quantity
    products_collection.update_one({'_id': order['product_id']}, {'$inc': {'quantity': order['quantity']}})
    order_customers_collection.delete_one({'order_id': object_id})
    orders_collection.delete_one({'_id': object_id})
    return jsonify({'message': 'Order deleted successfully'})

# ------------------ DASHBOARD ------------------
@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    total_products = products_collection.count_documents({})
    low_stock_products = products_collection.count_documents({'$expr': {'$lt': ['$quantity', '$reorder_threshold']}})
    recent_orders = list(orders_collection.find().sort('created_at', -1).limit(5))
    enriched_recent_orders = []
    for order in recent_orders:
        product = products_collection.find_one({'_id': order['product_id']})
        enriched_recent_orders.append({
            'id': str(order['_id']),
            'product_name': product['name'] if product else 'Unknown Product',
            'quantity': order['quantity'],
            'total_amount': order['total_amount'],
            'created_at': order['created_at'].isoformat()
        })
    return jsonify({
        'total_products': total_products,
        'low_stock_count': low_stock_products,
        'recent_orders': enriched_recent_orders
    })

@app.route('/api/dashboard/low-stock', methods=['GET'])
def get_low_stock_products():
    products = list(products_collection.find({'$expr': {'$lt': ['$quantity', '$reorder_threshold']}}))
    return jsonify([{
        'id': str(p['_id']),
        'name': p['name'],
        'quantity': p['quantity'],
        'reorder_threshold': p['reorder_threshold']
    } for p in products])

# Dashboard routes
@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    total_products = products_collection.count_documents({})
    low_stock_products = products_collection.count_documents({
        '$expr': {'$lt': ['$quantity', '$reorder_threshold']}
    })
    recent_orders = list(orders_collection.find().sort('created_at', -1).limit(5))
    
    # Enrich recent orders with product names
    enriched_recent_orders = []
    for order in recent_orders:
        product = products_collection.find_one({'_id': order['product_id']})
        enriched_recent_orders.append({
            'id': str(order['_id']),
            'product_name': product['name'] if product else 'Unknown Product',
            'quantity': order['quantity'],
            'total_amount': order['total_amount'],
            'created_at': order['created_at'].isoformat()
        })
    
    return jsonify({
        'total_products': total_products,
        'low_stock_count': low_stock_products,
        'recent_orders': enriched_recent_orders
    })

@app.route('/api/dashboard/low-stock', methods=['GET'])
def get_low_stock_products():
    products = list(products_collection.find({
        '$expr': {'$lt': ['$quantity', '$reorder_threshold']}
    }))
    
    return jsonify([{
        'id': str(p['_id']),
        'name': p['name'],
        'quantity': p['quantity'],
        'reorder_threshold': p['reorder_threshold']
    } for p in products])

# AI Insights endpoint
@app.route('/api/ai-insights', methods=['GET'])
def get_ai_insights():
    # Get all products and orders
    products = list(products_collection.find())
    orders = list(orders_collection.find().sort('created_at', -1).limit(20))
    
    insights = {
        'stock_recommendations': [],
        'sales_analysis': {},
        'trending_products': [],
        'risk_alerts': [],
        'optimization_tips': []
    }
    
    # Stock recommendations based on order history
    for product in products:
        product_orders = [o for o in orders if o['product_id'] == product['_id']]
        total_ordered = sum(o['quantity'] for o in product_orders)
        
        if product_orders:
            avg_order_size = total_ordered / len(product_orders)
            days_since_last_order = (datetime.utcnow() - product_orders[0]['created_at']).days
            
            # Stock recommendation logic
            if product['quantity'] < product['reorder_threshold']:
                recommended_stock = max(product['reorder_threshold'] * 2, int(avg_order_size * 3))
                insights['stock_recommendations'].append({
                    'product_name': product['name'],
                    'current_stock': product['quantity'],
                    'recommended_stock': recommended_stock,
                    'reason': 'Low stock alert - immediate restocking needed',
                    'priority': 'High'
                })
            elif product['quantity'] < product['reorder_threshold'] * 1.5:
                recommended_stock = int(avg_order_size * 2)
                insights['stock_recommendations'].append({
                    'product_name': product['name'],
                    'current_stock': product['quantity'],
                    'recommended_stock': recommended_stock,
                    'reason': 'Stock below optimal level - consider restocking',
                    'priority': 'Medium'
                })
    
    # Sales analysis
    if orders:
        total_revenue = sum(o['total_amount'] for o in orders)
        avg_order_value = total_revenue / len(orders)
        insights['sales_analysis'] = {
            'total_orders': len(orders),
            'total_revenue': total_revenue,
            'average_order_value': avg_order_value,
            'period': 'Last 20 orders'
        }
    
    # Trending products (most ordered)
    product_order_counts = {}
    for order in orders:
        product_id_str = str(order['product_id'])
        product_order_counts[product_id_str] = product_order_counts.get(product_id_str, 0) + order['quantity']
    
    trending_products = sorted(product_order_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    for product_id_str, total_ordered in trending_products:
        try:
            product_id = ObjectId(product_id_str)
            product = products_collection.find_one({'_id': product_id})
            if product:
                insights['trending_products'].append({
                    'product_name': product['name'],
                    'total_ordered': total_ordered,
                    'current_stock': product['quantity']
                })
        except:
            continue
    
    # Risk alerts
    for product in products:
        if product['quantity'] == 0:
            insights['risk_alerts'].append({
                'type': 'Out of Stock',
                'product_name': product['name'],
                'message': f"{product['name']} is completely out of stock!"
            })
        elif product['quantity'] < 2:
            insights['risk_alerts'].append({
                'type': 'Critical Stock',
                'product_name': product['name'],
                'message': f"{product['name']} has only {product['quantity']} units left!"
            })
    
    # Optimization tips
    low_stock_count = len([p for p in products if p['quantity'] < p['reorder_threshold']])
    if low_stock_count > 2:
        insights['optimization_tips'].append({
            'tip': 'Multiple products are low on stock. Consider bulk ordering to reduce shipping costs.',
            'impact': 'Cost savings and better stock management'
        })
    
    if len(orders) > 10:
        insights['optimization_tips'].append({
            'tip': 'High order volume detected. Consider implementing automated reorder points.',
            'impact': 'Reduced manual intervention and stockouts'
        })
    
    return jsonify(insights)

# Customer routes
@app.route('/api/customers', methods=['GET'])
def get_customers():
    customers = list(customers_collection.find())
    return jsonify([serialize_id(customer) for customer in customers])

@app.route('/api/customers/<customer_id>', methods=['GET'])
def get_customer(customer_id):
    object_id = safe_object_id(customer_id)
    if not object_id:
        return jsonify({'error': 'Invalid customer ID'}), 400
    
    customer = customers_collection.find_one({'_id': object_id})
    if not customer:
        return jsonify({'error': 'Customer not found'}), 404
    
    return jsonify(serialize_id(customer))

@app.route('/api/customers', methods=['POST'])
def create_customer():
    data = request.get_json()
    customer = {
        'name': data['name'],
        'contact': data['contact'],
        'address': data['address'],
        'created_at': datetime.utcnow()
    }
    result = customers_collection.insert_one(customer)
    customer['_id'] = result.inserted_id
    return jsonify(serialize_id(customer)), 201

@app.route('/api/customers/<customer_id>', methods=['PUT'])
def update_customer(customer_id):
    object_id = safe_object_id(customer_id)
    if not object_id:
        return jsonify({'error': 'Invalid customer ID'}), 400
    
    data = request.get_json()
    update_data = {
        'name': data['name'],
        'contact': data['contact'],
        'address': data['address']
    }
    
    result = customers_collection.update_one(
        {'_id': object_id},
        {'$set': update_data}
    )
    
    if result.matched_count == 0:
        return jsonify({'error': 'Customer not found'}), 404
    
    # Get updated customer
    updated_customer = customers_collection.find_one({'_id': object_id})
    return jsonify(serialize_id(updated_customer))

@app.route('/api/customers/<customer_id>', methods=['DELETE'])
def delete_customer(customer_id):
    object_id = safe_object_id(customer_id)
    if not object_id:
        return jsonify({'error': 'Invalid customer ID'}), 400
    
    result = customers_collection.delete_one({'_id': object_id})
    
    if result.deleted_count == 0:
        return jsonify({'error': 'Customer not found'}), 404
    
    return jsonify({'message': 'Customer deleted successfully'})

# Supplier routes
@app.route('/api/suppliers', methods=['GET'])
def get_suppliers():
    suppliers = list(suppliers_collection.find())
    return jsonify([serialize_id(supplier) for supplier in suppliers])

@app.route('/api/suppliers/<supplier_id>', methods=['GET'])
def get_supplier(supplier_id):
    object_id = safe_object_id(supplier_id)
    if not object_id:
        return jsonify({'error': 'Invalid supplier ID'}), 400
    
    supplier = suppliers_collection.find_one({'_id': object_id})
    if not supplier:
        return jsonify({'error': 'Supplier not found'}), 404
    
    return jsonify(serialize_id(supplier))

@app.route('/api/suppliers', methods=['POST'])
def create_supplier():
    data = request.get_json()
    supplier = {
        'name': data['name'],
        'contact': data['contact'],
        'address': data['address'],
        'created_at': datetime.utcnow()
    }
    result = suppliers_collection.insert_one(supplier)
    supplier['_id'] = result.inserted_id
    return jsonify(serialize_id(supplier)), 201

@app.route('/api/suppliers/<supplier_id>', methods=['PUT'])
def update_supplier(supplier_id):
    object_id = safe_object_id(supplier_id)
    if not object_id:
        return jsonify({'error': 'Invalid supplier ID'}), 400
    
    data = request.get_json()
    update_data = {
        'name': data['name'],
        'contact': data['contact'],
        'address': data['address']
    }
    
    result = suppliers_collection.update_one(
        {'_id': object_id},
        {'$set': update_data}
    )
    
    if result.matched_count == 0:
        return jsonify({'error': 'Supplier not found'}), 404
    
    # Get updated supplier
    updated_supplier = suppliers_collection.find_one({'_id': object_id})
    return jsonify(serialize_id(updated_supplier))

@app.route('/api/suppliers/<supplier_id>', methods=['DELETE'])
def delete_supplier(supplier_id):
    object_id = safe_object_id(supplier_id)
    if not object_id:
        return jsonify({'error': 'Invalid supplier ID'}), 400
    
    result = suppliers_collection.delete_one({'_id': object_id})
    
    if result.deleted_count == 0:
        return jsonify({'error': 'Supplier not found'}), 404
    
    return jsonify({'message': 'Supplier deleted successfully'})


    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
