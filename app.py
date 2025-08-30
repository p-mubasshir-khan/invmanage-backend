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
CORS(app, origins=["https://invmanage-frontend.vercel.app"], methods=["GET", "POST", "PUT", "DELETE"])

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

# Enable CORS for all origins (for local development)
CORS(app)

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
    return jsonify([serialize_id(product) for product in products])

@app.route('/api/products', methods=['POST'])
def create_product():
    data = request.get_json()
    product = {
        'name': data['name'],
        'quantity': data['quantity'],
        'price': data['price'],
        'reorder_threshold': data['reorder_threshold'],
        'created_at': datetime.utcnow()
    }
    result = products_collection.insert_one(product)
    product['_id'] = result.inserted_id
    return jsonify(serialize_id(product)), 201

@app.route('/api/products/<product_id>', methods=['PUT'])
def update_product(product_id):
    try:
        object_id = ObjectId(product_id)
    except:
        return jsonify({'error': 'Invalid product ID'}), 400
    
    data = request.get_json()
    update_data = {
        'name': data['name'],
        'quantity': data['quantity'],
        'price': data['price'],
        'reorder_threshold': data['reorder_threshold']
    }
    
    result = products_collection.update_one(
        {'_id': object_id},
        {'$set': update_data}
    )
    
    if result.matched_count == 0:
        return jsonify({'error': 'Product not found'}), 404
    
    # Get updated product
    updated_product = products_collection.find_one({'_id': object_id})
    return jsonify(serialize_id(updated_product))

@app.route('/api/products/<product_id>', methods=['DELETE'])
def delete_product(product_id):
    try:
        object_id = ObjectId(product_id)
    except:
        return jsonify({'error': 'Invalid product ID'}), 400
    
    result = products_collection.delete_one({'_id': object_id})
    
    if result.deleted_count == 0:
        return jsonify({'error': 'Product not found'}), 404
    
    return jsonify({'message': 'Product deleted successfully'})

# Order routes
@app.route('/api/orders', methods=['GET'])
def get_orders():
    orders = list(orders_collection.find().sort('created_at', -1))
    
    # Get all product IDs and customer IDs for efficient lookup
    product_ids = [order['product_id'] for order in orders]
    products = {str(p['_id']): p for p in products_collection.find({'_id': {'$in': product_ids}})}
    
    # Get customer mappings
    order_ids = [order['_id'] for order in orders]
    customer_mappings = list(order_customers_collection.find({'order_id': {'$in': order_ids}}))
    customer_ids = [mapping['customer_id'] for mapping in customer_mappings]
    customers = {str(c['_id']): c for c in customers_collection.find({'_id': {'$in': customer_ids}})}
    
    # Build order_id to customer_id mapping
    order_to_customer = {str(mapping['order_id']): str(mapping['customer_id']) for mapping in customer_mappings}
    
    # Enrich orders with product and customer info
    enriched_orders = []
    for order in orders:
        order_str_id = str(order['_id'])
        product = products.get(str(order['product_id']))
        customer_id = order_to_customer.get(order_str_id)
        customer = customers.get(customer_id) if customer_id else None
        
        enriched_order = {
            'id': order_str_id,
            'product_id': str(order['product_id']),
            'product_name': product['name'] if product else 'Unknown Product',
            'quantity': order['quantity'],
            'total_amount': order['total_amount'],
            'created_at': order['created_at'].isoformat(),
            'customer_id': customer_id,
            'customer_name': customer['name'] if customer else None
        }
        enriched_orders.append(enriched_order)
    
    return jsonify(enriched_orders)

@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.get_json()
    
    try:
        product_id = ObjectId(data['product_id'])
    except:
        return jsonify({'error': 'Invalid product ID'}), 400
    
    product = products_collection.find_one({'_id': product_id})
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    
    if product['quantity'] < data['quantity']:
        return jsonify({'error': 'Insufficient stock'}), 400
    
    # Calculate total amount
    total_amount = product['price'] * data['quantity']
    
    # Create order
    order = {
        'product_id': product_id,
        'quantity': data['quantity'],
        'total_amount': total_amount,
        'created_at': datetime.utcnow()
    }
    
    result = orders_collection.insert_one(order)
    order['_id'] = result.inserted_id
    
    # Update product quantity
    products_collection.update_one(
        {'_id': product_id},
        {'$inc': {'quantity': -data['quantity']}}
    )
    
    # Optional customer link
    customer_id = data.get('customer_id')
    if customer_id:
        try:
            customer_object_id = ObjectId(customer_id)
            customer = customers_collection.find_one({'_id': customer_object_id})
            if customer:
                link = {
                    'order_id': order['_id'],
                    'customer_id': customer_object_id,
                    'created_at': datetime.utcnow()
                }
                order_customers_collection.insert_one(link)
        except:
            pass  # Invalid customer ID, continue without linking
    
    # Build response
    resp = serialize_id(order)
    if customer_id:
        resp['customer_id'] = customer_id
        if customer:
            resp['customer_name'] = customer['name']
    
    return jsonify(resp), 201

@app.route('/api/orders/<order_id>', methods=['DELETE'])
def delete_order(order_id):
    try:
        object_id = ObjectId(order_id)
    except:
        return jsonify({'error': 'Invalid order ID'}), 400
    
    order = orders_collection.find_one({'_id': object_id})
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    
    # Restore product quantity
    products_collection.update_one(
        {'_id': order['product_id']},
        {'$inc': {'quantity': order['quantity']}}
    )
    
    # Delete customer link if exists
    order_customers_collection.delete_one({'order_id': object_id})
    
    # Delete order
    orders_collection.delete_one({'_id': object_id})
    
    return jsonify({'message': 'Order deleted successfully'})

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
    try:
        object_id = ObjectId(customer_id)
    except:
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
    try:
        object_id = ObjectId(customer_id)
    except:
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
    try:
        object_id = ObjectId(customer_id)
    except:
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
    try:
        object_id = ObjectId(supplier_id)
    except:
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
    try:
        object_id = ObjectId(supplier_id)
    except:
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
    try:
        object_id = ObjectId(supplier_id)
    except:
        return jsonify({'error': 'Invalid supplier ID'}), 400
    
    result = suppliers_collection.delete_one({'_id': object_id})
    
    if result.deleted_count == 0:
        return jsonify({'error': 'Supplier not found'}), 404
    
    return jsonify({'message': 'Supplier deleted successfully'})

if __name__ == '__main__':
    # Seed some products if database is empty
    if products_collection.count_documents({}) == 0:
        seed_products = [
            {'name': 'Laptop', 'quantity': 15, 'price': 999.99, 'reorder_threshold': 10},
            {'name': 'Mouse', 'quantity': 5, 'price': 25.99, 'reorder_threshold': 10},
            {'name': 'Keyboard', 'quantity': 8, 'price': 75.50, 'reorder_threshold': 10},
            {'name': 'Monitor', 'quantity': 12, 'price': 299.99, 'reorder_threshold': 10},
            {'name': 'Headphones', 'quantity': 3, 'price': 89.99, 'reorder_threshold': 10},
        ]
        for product in seed_products:
            product['created_at'] = datetime.utcnow()
            products_collection.insert_one(product)
        print("Seed products added to database!")

        # Ensure additional demo products exist
        additional_products = [
            {'name': 'Smartphone', 'quantity': 20, 'price': 599.99, 'reorder_threshold': 10},
            {'name': 'Tablet', 'quantity': 10, 'price': 399.99, 'reorder_threshold': 8},
            {'name': 'Printer', 'quantity': 6, 'price': 199.99, 'reorder_threshold': 4},
            {'name': 'USB-C Cable', 'quantity': 50, 'price': 9.99, 'reorder_threshold': 25},
            {'name': 'External Hard Drive', 'quantity': 14, 'price': 129.99, 'reorder_threshold': 6},
            {'name': 'Webcam', 'quantity': 18, 'price': 59.99, 'reorder_threshold': 8},
            {'name': 'Wireless Router', 'quantity': 9, 'price': 149.99, 'reorder_threshold': 5},
        ]
        for p in additional_products:
            p['created_at'] = datetime.utcnow()
            products_collection.insert_one(p)
        print("Additional demo products added to database!")
    
    # Seed some customers if database is empty
    if customers_collection.count_documents({}) == 0:
        seed_customers = [
            {'name': 'John Doe', 'contact': 'john@email.com', 'address': '123 Main St, City, State'},
            {'name': 'Jane Smith', 'contact': 'jane@email.com', 'address': '456 Oak Ave, Town, State'},
            {'name': 'Bob Johnson', 'contact': 'bob@email.com', 'address': '789 Pine Rd, Village, State'},
        ]
        for customer in seed_customers:
            customer['created_at'] = datetime.utcnow()
            customers_collection.insert_one(customer)
        print("Seed customers added to database!")
    
    # Seed some suppliers if database is empty
    if suppliers_collection.count_documents({}) == 0:
        seed_suppliers = [
            {'name': 'Tech Supplies Inc', 'contact': 'sales@techsupplies.com', 'address': '100 Tech Blvd, Tech City, State'},
            {'name': 'Office Equipment Co', 'contact': 'info@officeequip.com', 'address': '200 Office Dr, Business Town, State'},
            {'name': 'Computer Parts Ltd', 'contact': 'orders@computerparts.com', 'address': '300 Hardware Way, Parts City, State'},
        ]
        for supplier in seed_suppliers:
            supplier['created_at'] = datetime.utcnow()
            suppliers_collection.insert_one(supplier)
        print("Seed suppliers added to database!")
    
    # Seed some sample orders if database is empty
    if orders_collection.count_documents({}) == 0:
        # Get products for creating orders
        laptop = products_collection.find_one({'name': 'Laptop'})
        mouse = products_collection.find_one({'name': 'Mouse'})
        keyboard = products_collection.find_one({'name': 'Keyboard'})
        monitor = products_collection.find_one({'name': 'Monitor'})
        headphones = products_collection.find_one({'name': 'Headphones'})
        
        if laptop and mouse and keyboard and monitor and headphones:
            seed_orders = [
                {'product_id': laptop['_id'], 'quantity': 2, 'total_amount': laptop['price'] * 2},
                {'product_id': mouse['_id'], 'quantity': 5, 'total_amount': mouse['price'] * 5},
                {'product_id': keyboard['_id'], 'quantity': 3, 'total_amount': keyboard['price'] * 3},
                {'product_id': monitor['_id'], 'quantity': 1, 'total_amount': monitor['price'] * 1},
                {'product_id': headphones['_id'], 'quantity': 2, 'total_amount': headphones['price'] * 2},
                {'product_id': laptop['_id'], 'quantity': 1, 'total_amount': laptop['price'] * 1},
                {'product_id': mouse['_id'], 'quantity': 3, 'total_amount': mouse['price'] * 3},
            ]
            
            # Update product quantities
            products_collection.update_one(
                {'_id': laptop['_id']}, 
                {'$inc': {'quantity': -3}}  # 2 + 1 orders
            )
            products_collection.update_one(
                {'_id': mouse['_id']}, 
                {'$inc': {'quantity': -8}}   # 5 + 3 orders
            )
            products_collection.update_one(
                {'_id': keyboard['_id']}, 
                {'$inc': {'quantity': -3}}
            )
            products_collection.update_one(
                {'_id': monitor['_id']}, 
                {'$inc': {'quantity': -1}}
            )
            products_collection.update_one(
                {'_id': headphones['_id']}, 
                {'$inc': {'quantity': -2}}
            )
            
            for order in seed_orders:
                order['created_at'] = datetime.utcnow()
                orders_collection.insert_one(order)
            print("Seed orders added to database!")

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
