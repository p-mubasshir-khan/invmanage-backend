# MongoDB Setup Guide

## Prerequisites

1. **Install MongoDB Community Edition**:
   - Download from: https://www.mongodb.com/try/download/community
   - Or use Docker: `docker run -d -p 27017:27017 --name mongodb mongo:latest`

2. **Install Python Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

The application is configured to connect to MongoDB using the `.env` file:

```env
MONGO_URI=mongodb://localhost:27017/
SECRET_KEY=your-secret-key-here
```

## Running the Application

1. **Start MongoDB** (if not using Docker):
   ```bash
   # Windows
   net start MongoDB
   
   # macOS/Linux
   sudo systemctl start mongod
   ```

2. **Run the Flask application**:
   ```bash
   python app.py
   ```

## MongoDB Atlas (Cloud) Setup

If you prefer to use MongoDB Atlas (cloud):

1. Create a free account at https://www.mongodb.com/atlas
2. Create a new cluster
3. Get your connection string
4. Update `.env`:
   ```env
   MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/
   ```

## Database Structure

The application will automatically create these collections:
- `products` - Product inventory
- `orders` - Customer orders
- `customers` - Customer information
- `suppliers` - Supplier information
- `order_customers` - Order-customer relationships

## Data Seeding

The application automatically seeds sample data on first run:
- 12 demo products (Laptops, Mice, Keyboards, etc.)
- 3 sample customers
- 3 sample suppliers
- 7 sample orders

## Troubleshooting

1. **Connection Error**: Ensure MongoDB is running and accessible
2. **Port Issues**: Default MongoDB port is 27017
3. **Authentication**: For production, add username/password to MONGO_URI
4. **Network**: For remote connections, ensure firewall allows MongoDB port

## Migration from SQLite

- ✅ All SQLAlchemy models replaced with MongoDB collections
- ✅ All API endpoints updated for MongoDB operations
- ✅ ObjectId handling implemented
- ✅ Data serialization updated
- ✅ Seeding logic migrated
