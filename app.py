from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, Session, relationship

# Database configuration
DATABASE_URL = "mysql+mysqlconnector://todo_user:pass@localhost/ecommerce_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Define Product model
class ProductDB(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    price = Column(Float, nullable=False)
    description = Column(String(255), nullable=True)  # New description column

# Define CartItem model
class CartItemDB(Base):
    __tablename__ = "cart_items"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey('products.id', ondelete='CASCADE'))
    quantity = Column(Integer, nullable=False)

    # Relationships
    product = relationship("ProductDB")

# Create the database tables
Base.metadata.create_all(bind=engine)

# Define Pydantic Schemas
class Product(BaseModel):
    id: int  # Optional; can be removed if you want to keep it clean
    name: str
    price: float
    description: str = None  # Optional field

    class Config:
        from_attributes = True  # Update for Pydantic v2 compatibility

class CartItem(BaseModel):
    product_id: int
    quantity: int

    class Config:
        from_attributes = True  # Update for Pydantic v2 compatibility

class CartItemResponse(BaseModel):
    product_id: int
    product_name: str
    quantity: int
    price_per_unit: float
    price_as_per_count: float

class CartTotalResponse(BaseModel):
    items: list[CartItemResponse]
    total_price: float

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()

# Create new products (Accepts an array of products)
@app.post("/products/", response_model=list[Product])
def create_products(products: list[Product], db: Session = Depends(get_db)):
    created_products = []
    
    for product in products:
        db_product = ProductDB(name=product.name, price=product.price, description=product.description)
        db.add(db_product)
        db.commit()
        db.refresh(db_product)
        created_products.append(db_product)
    
    return created_products

# Get all products
@app.get("/products/", response_model=list[Product])
def get_products(db: Session = Depends(get_db)):
    return db.query(ProductDB).all()

# Get product by ID
@app.get("/products/{product_id}", response_model=Product)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(ProductDB).filter(ProductDB.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

# Delete product by ID
@app.delete("/products/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(ProductDB).filter(ProductDB.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    db.delete(product)
    db.commit()
    return {"message": "Product deleted"}

# Add item to cart
@app.post("/cart/", response_model=CartItem)
def add_to_cart(product_id: int, quantity: int, db: Session = Depends(get_db)):
    product = db.query(ProductDB).filter(ProductDB.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    cart_item = db.query(CartItemDB).filter(CartItemDB.product_id == product_id).first()
    if cart_item:
        cart_item.quantity += quantity
    else:
        cart_item = CartItemDB(product_id=product_id, quantity=quantity)
        db.add(cart_item)

    db.commit()
    db.refresh(cart_item)
    return CartItem(product_id=cart_item.product_id, quantity=cart_item.quantity)

# Get cart total price and view cart items
@app.get("/cart/total_price/", response_model=CartTotalResponse)
def get_cart_total_price(db: Session = Depends(get_db)):
    total_price = 0.0
    cart_items = db.query(CartItemDB).all()
    items_response = []

    for item in cart_items:
        item_total = item.quantity * item.product.price
        total_price += item_total
        
        # Create a response item
        items_response.append(
            CartItemResponse(
                product_id=item.product.id,
                product_name=item.product.name,
                quantity=item.quantity,
                price_per_unit=item.product.price,
                price_as_per_count=item_total
            )
        )

    return CartTotalResponse(items=items_response, total_price=total_price)

# Remove item from cart and delete product
@app.delete("/cart/remove/{cart_item_id}", response_model=CartItem)
def remove_cart_item(cart_item_id: int, db: Session = Depends(get_db)):
    # Get the cart item
    cart_item = db.query(CartItemDB).filter(CartItemDB.id == cart_item_id).first()
    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found")

    # Get the product associated with the cart item
    product_id = cart_item.product_id

    # Delete the cart item
    db.delete(cart_item)
    db.commit()

    # Delete the product
    product_to_delete = db.query(ProductDB).filter(ProductDB.id == product_id).first()
    if product_to_delete:
        db.delete(product_to_delete)
        db.commit()

    return CartItem(product_id=product_id, quantity=0)  # Return the removed cart item info
