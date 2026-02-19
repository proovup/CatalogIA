from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from ecoia.db.models import Product


class ProductService:
    def __init__(self, db: Session):
        self.db = db

    def get_product(self, product_id: UUID) -> Optional[Product]:
        """Get a product by ID"""
        return self.db.query(Product).filter(Product.id == product_id).first()

    def get_products_by_document(self, document_id: UUID) -> List[Product]:
        """Get all products for a document"""
        return self.db.query(Product).filter(Product.document_id == document_id).all()

    def create_product(self, product_data: dict) -> Product:
        """Create a new product"""
        product = Product(**product_data)
        self.db.add(product)
        self.db.commit()
        self.db.refresh(product)
        return product

    def update_product(self, product_id: UUID, product_data: dict) -> Optional[Product]:
        """Update a product"""
        product = self.get_product(product_id)
        if product:
            for key, value in product_data.items():
                if hasattr(product, key):
                    setattr(product, key, value)
            self.db.commit()
            self.db.refresh(product)
        return product

    def delete_product(self, product_id: UUID) -> bool:
        """Delete a product"""
        product = self.get_product(product_id)
        if product:
            self.db.delete(product)
            self.db.commit()
            return True
        return False

    def get_all_products(self, skip: int = 0, limit: int = 100) -> List[Product]:
        """Get all products with pagination"""
        return self.db.query(Product).offset(skip).limit(limit).all()
