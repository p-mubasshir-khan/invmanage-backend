from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-here'

db = SQLAlchemy(app)
CORS(app)

# Models
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, default=0)
    price = db.Column(db.Float, nullable=False)
    reorder_threshold = db.Column(db.Integer, default=10)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    product = db.relationship('Product', backref=db.backref('orders', lazy=True))

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Link each order to one customer without altering existing Order table
class OrderCustomer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False, unique=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    products = Product.query.all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'quantity': p.quantity,
        'price': p.price,
        'reorder_threshold': p.reorder_threshold,
        'created_at': p.created_at.isoformat()
    } for p in products])

@app.route('/api/products', methods=['POST'])
def create_product():
    data = request.get_json()
    product = Product(
        name=data['name'],
        quantity=data['quantity'],
        price=data['price'],
        reorder_threshold=data['reorder_threshold']
    )
    db.session.add(product)
    db.session.commit()
    return jsonify({
        'id': product.id,
        'name': product.name,
        'quantity': product.quantity,
        'price': product.price,
        'reorder_threshold': product.reorder_threshold,
        'created_at': product.created_at.isoformat()
    }), 201

@app.route('/api/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    product = Product.query.get_or_404(product_id)
    data = request.get_json()
    
    product.name = data['name']
    product.quantity = data['quantity']
    product.price = data['price']
    product.reorder_threshold = data['reorder_threshold']
    
    db.session.commit()
    return jsonify({
        'id': product.id,
        'name': product.name,
        'quantity': product.quantity,
        'price': product.price,
        'reorder_threshold': product.reorder_threshold,
        'created_at': product.created_at.isoformat()
    })

@app.route('/api/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    return jsonify({'message': 'Product deleted successfully'})

# Order routes
@app.route('/api/orders', methods=['GET'])
def get_orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    # Preload order->customer mapping
    order_ids = [o.id for o in orders]
    mappings = OrderCustomer.query.filter(OrderCustomer.order_id.in_(order_ids)).all() if order_ids else []
    order_id_to_customer = {m.order_id: m.customer_id for m in mappings}
    customers = {}
    if order_id_to_customer:
        customer_ids = list(set(order_id_to_customer.values()))
        for c in Customer.query.filter(Customer.id.in_(customer_ids)).all():
            customers[c.id] = c
    return jsonify([{
        'id': o.id,
        'product_id': o.product_id,
        'product_name': o.product.name,
        'quantity': o.quantity,
        'total_amount': o.total_amount,
        'created_at': o.created_at.isoformat(),
        'customer_id': order_id_to_customer.get(o.id),
        'customer_name': customers.get(order_id_to_customer.get(o.id)).name if order_id_to_customer.get(o.id) and customers.get(order_id_to_customer.get(o.id)) else None
    } for o in orders])

@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.get_json()
    product = Product.query.get_or_404(data['product_id'])
    
    if product.quantity < data['quantity']:
        return jsonify({'error': 'Insufficient stock'}), 400
    
    # Calculate total amount
    total_amount = product.price * data['quantity']
    
    # Create order
    order = Order(
        product_id=data['product_id'],
        quantity=data['quantity'],
        total_amount=total_amount
    )
    
    # Update product quantity
    product.quantity -= data['quantity']
    
    db.session.add(order)
    db.session.commit()

    # Optional customer link
    customer_id = data.get('customer_id')
    if customer_id:
        customer = Customer.query.get_or_404(customer_id)
        link = OrderCustomer(order_id=order.id, customer_id=customer.id)
        db.session.add(link)
        db.session.commit()
    
    # Build response with optional customer
    resp = {
        'id': order.id,
        'product_id': order.product_id,
        'product_name': order.product.name,
        'quantity': order.quantity,
        'total_amount': order.total_amount,
        'created_at': order.created_at.isoformat()
    }
    if customer_id:
        resp['customer_id'] = customer_id
        resp['customer_name'] = customer.name
    return jsonify(resp), 201

@app.route('/api/orders/<int:order_id>', methods=['DELETE'])
def delete_order(order_id):
    order = Order.query.get_or_404(order_id)
    product = Product.query.get(order.product_id)
    if product:
        product.quantity += order.quantity
    # Delete customer link if exists
    link = OrderCustomer.query.filter_by(order_id=order.id).first()
    if link:
        db.session.delete(link)
    db.session.delete(order)
    db.session.commit()
    return jsonify({'message': 'Order deleted successfully'})

# Dashboard routes
@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    total_products = Product.query.count()
    low_stock_products = Product.query.filter(Product.quantity < Product.reorder_threshold).count()
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
    
    return jsonify({
        'total_products': total_products,
        'low_stock_count': low_stock_products,
        'recent_orders': [{
            'id': o.id,
            'product_name': o.product.name,
            'quantity': o.quantity,
            'total_amount': o.total_amount,
            'created_at': o.created_at.isoformat()
        } for o in recent_orders]
    })

@app.route('/api/dashboard/low-stock', methods=['GET'])
def get_low_stock_products():
    products = Product.query.filter(Product.quantity < Product.reorder_threshold).all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'quantity': p.quantity,
        'reorder_threshold': p.reorder_threshold
    } for p in products])

# AI Insights endpoint
@app.route('/api/ai-insights', methods=['GET'])
def get_ai_insights():
     # Get all products and orders
     products = Product.query.all()
     orders = Order.query.order_by(Order.created_at.desc()).limit(20).all()
     
     insights = {
         'stock_recommendations': [],
         'sales_analysis': {},
         'trending_products': [],
         'risk_alerts': [],
         'optimization_tips': []
     }
     
     # Stock recommendations based on order history
     for product in products:
         product_orders = [o for o in orders if o.product_id == product.id]
         total_ordered = sum(o.quantity for o in product_orders)
         
         if product_orders:
             avg_order_size = total_ordered / len(product_orders)
             days_since_last_order = (datetime.utcnow() - product_orders[0].created_at).days
             
             # Stock recommendation logic
             if product.quantity < product.reorder_threshold:
                 recommended_stock = max(product.reorder_threshold * 2, int(avg_order_size * 3))
                 insights['stock_recommendations'].append({
                     'product_name': product.name,
                     'current_stock': product.quantity,
                     'recommended_stock': recommended_stock,
                     'reason': 'Low stock alert - immediate restocking needed',
                     'priority': 'High'
                 })
             elif product.quantity < product.reorder_threshold * 1.5:
                 recommended_stock = int(avg_order_size * 2)
                 insights['stock_recommendations'].append({
                     'product_name': product.name,
                     'current_stock': product.quantity,
                     'recommended_stock': recommended_stock,
                     'reason': 'Stock below optimal level - consider restocking',
                     'priority': 'Medium'
                 })
     
     # Sales analysis
     if orders:
         total_revenue = sum(o.total_amount for o in orders)
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
         product_order_counts[order.product_id] = product_order_counts.get(order.product_id, 0) + order.quantity
     
     trending_products = sorted(product_order_counts.items(), key=lambda x: x[1], reverse=True)[:3]
     for product_id, total_ordered in trending_products:
         product = Product.query.get(product_id)
         if product:
             insights['trending_products'].append({
                 'product_name': product.name,
                 'total_ordered': total_ordered,
                 'current_stock': product.quantity
             })
     
     # Risk alerts
     for product in products:
         if product.quantity == 0:
             insights['risk_alerts'].append({
                 'type': 'Out of Stock',
                 'product_name': product.name,
                 'message': f'{product.name} is completely out of stock!'
             })
         elif product.quantity < 2:
             insights['risk_alerts'].append({
                 'type': 'Critical Stock',
                 'product_name': product.name,
                 'message': f'{product.name} has only {product.quantity} units left!'
             })
     
     # Optimization tips
     low_stock_count = len([p for p in products if p.quantity < p.reorder_threshold])
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
    customers = Customer.query.all()
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'contact': c.contact,
        'address': c.address,
        'created_at': c.created_at.isoformat()
    } for c in customers])

@app.route('/api/customers/<int:customer_id>', methods=['GET'])
def get_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    return jsonify({
        'id': customer.id,
        'name': customer.name,
        'contact': customer.contact,
        'address': customer.address,
        'created_at': customer.created_at.isoformat()
    })

@app.route('/api/customers', methods=['POST'])
def create_customer():
    data = request.get_json()
    customer = Customer(
        name=data['name'],
        contact=data['contact'],
        address=data['address']
    )
    db.session.add(customer)
    db.session.commit()
    return jsonify({
        'id': customer.id,
        'name': customer.name,
        'contact': customer.contact,
        'address': customer.address,
        'created_at': customer.created_at.isoformat()
    }), 201

@app.route('/api/customers/<int:customer_id>', methods=['PUT'])
def update_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    data = request.get_json()
    
    customer.name = data['name']
    customer.contact = data['contact']
    customer.address = data['address']
    
    db.session.commit()
    return jsonify({
        'id': customer.id,
        'name': customer.name,
        'contact': customer.contact,
        'address': customer.address,
        'created_at': customer.created_at.isoformat()
    })

@app.route('/api/customers/<int:customer_id>', methods=['DELETE'])
def delete_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    db.session.delete(customer)
    db.session.commit()
    return jsonify({'message': 'Customer deleted successfully'})

# Supplier routes
@app.route('/api/suppliers', methods=['GET'])
def get_suppliers():
    suppliers = Supplier.query.all()
    return jsonify([{
        'id': s.id,
        'name': s.name,
        'contact': s.contact,
        'address': s.address,
        'created_at': s.created_at.isoformat()
    } for s in suppliers])

@app.route('/api/suppliers/<int:supplier_id>', methods=['GET'])
def get_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    return jsonify({
        'id': supplier.id,
        'name': supplier.name,
        'contact': supplier.contact,
        'address': supplier.address,
        'created_at': supplier.created_at.isoformat()
    })

@app.route('/api/suppliers', methods=['POST'])
def create_supplier():
    data = request.get_json()
    supplier = Supplier(
        name=data['name'],
        contact=data['contact'],
        address=data['address']
    )
    db.session.add(supplier)
    db.session.commit()
    return jsonify({
        'id': supplier.id,
        'name': supplier.name,
        'contact': supplier.contact,
        'address': supplier.address,
        'created_at': supplier.created_at.isoformat()
    }), 201

@app.route('/api/suppliers/<int:supplier_id>', methods=['PUT'])
def update_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    data = request.get_json()
    
    supplier.name = data['name']
    supplier.contact = data['contact']
    supplier.address = data['address']
    
    db.session.commit()
    return jsonify({
        'id': supplier.id,
        'name': supplier.name,
        'contact': supplier.contact,
        'address': supplier.address,
        'created_at': supplier.created_at.isoformat()
    })

@app.route('/api/suppliers/<int:supplier_id>', methods=['DELETE'])
def delete_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    db.session.delete(supplier)
    db.session.commit()
    return jsonify({'message': 'Supplier deleted successfully'})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Seed some products if database is empty
        if Product.query.count() == 0:
            seed_products = [
                Product(name='Laptop', quantity=15, price=999.99, reorder_threshold=10),
                Product(name='Mouse', quantity=5, price=25.99, reorder_threshold=10),
                Product(name='Keyboard', quantity=8, price=75.50, reorder_threshold=10),
                Product(name='Monitor', quantity=12, price=299.99, reorder_threshold=10),
                Product(name='Headphones', quantity=3, price=89.99, reorder_threshold=10),
            ]
            for product in seed_products:
                db.session.add(product)
            db.session.commit()
            print("Seed products added to database!")

        # Ensure additional demo products exist (idempotent by name)
        additional_products = [
            { 'name': 'Smartphone', 'quantity': 20, 'price': 599.99, 'reorder_threshold': 10 },
            { 'name': 'Tablet', 'quantity': 10, 'price': 399.99, 'reorder_threshold': 8 },
            { 'name': 'Printer', 'quantity': 6, 'price': 199.99, 'reorder_threshold': 4 },
            { 'name': 'USB-C Cable', 'quantity': 50, 'price': 9.99, 'reorder_threshold': 25 },
            { 'name': 'External Hard Drive', 'quantity': 14, 'price': 129.99, 'reorder_threshold': 6 },
            { 'name': 'Webcam', 'quantity': 18, 'price': 59.99, 'reorder_threshold': 8 },
            { 'name': 'Wireless Router', 'quantity': 9, 'price': 149.99, 'reorder_threshold': 5 },
        ]
        added_any = False
        for p in additional_products:
            if not Product.query.filter_by(name=p['name']).first():
                db.session.add(Product(
                    name=p['name'],
                    quantity=p['quantity'],
                    price=p['price'],
                    reorder_threshold=p['reorder_threshold']
                ))
                added_any = True
        if added_any:
            db.session.commit()
            print("Additional demo products added to database!")
        
        # Seed some customers if database is empty
        if Customer.query.count() == 0:
            seed_customers = [
                Customer(name='John Doe', contact='john@email.com', address='123 Main St, City, State'),
                Customer(name='Jane Smith', contact='jane@email.com', address='456 Oak Ave, Town, State'),
                Customer(name='Bob Johnson', contact='bob@email.com', address='789 Pine Rd, Village, State'),
            ]
            for customer in seed_customers:
                db.session.add(customer)
            db.session.commit()
            print("Seed customers added to database!")
        
        # Seed some suppliers if database is empty
        if Supplier.query.count() == 0:
            seed_suppliers = [
                Supplier(name='Tech Supplies Inc', contact='sales@techsupplies.com', address='100 Tech Blvd, Tech City, State'),
                Supplier(name='Office Equipment Co', contact='info@officeequip.com', address='200 Office Dr, Business Town, State'),
                Supplier(name='Computer Parts Ltd', contact='orders@computerparts.com', address='300 Hardware Way, Parts City, State'),
            ]
            for supplier in seed_suppliers:
                db.session.add(supplier)
            db.session.commit()
            print("Seed suppliers added to database!")
        
                # Seed some sample orders if database is empty
        if Order.query.count() == 0:
             # Get products for creating orders
             laptop = Product.query.filter_by(name='Laptop').first()
             mouse = Product.query.filter_by(name='Mouse').first()
             keyboard = Product.query.filter_by(name='Keyboard').first()
             monitor = Product.query.filter_by(name='Monitor').first()
             headphones = Product.query.filter_by(name='Headphones').first()
             
             if laptop and mouse and keyboard and monitor and headphones:
                 seed_orders = [
                     Order(product_id=laptop.id, quantity=2, total_amount=laptop.price * 2),
                     Order(product_id=mouse.id, quantity=5, total_amount=mouse.price * 5),
                     Order(product_id=keyboard.id, quantity=3, total_amount=keyboard.price * 3),
                     Order(product_id=monitor.id, quantity=1, total_amount=monitor.price * 1),
                     Order(product_id=headphones.id, quantity=2, total_amount=headphones.price * 2),
                     Order(product_id=laptop.id, quantity=1, total_amount=laptop.price * 1),
                     Order(product_id=mouse.id, quantity=3, total_amount=mouse.price * 3),
                 ]
                 
                 # Update product quantities
                 laptop.quantity -= 3  # 2 + 1 orders
                 mouse.quantity -= 8   # 5 + 3 orders
                 keyboard.quantity -= 3
                 monitor.quantity -= 1
                 headphones.quantity -= 2
                 
                 for order in seed_orders:
                     db.session.add(order)
                 db.session.commit()
                 print("Seed orders added to database!")
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
