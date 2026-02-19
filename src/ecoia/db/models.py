import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    DateTime,
    String,
    Integer,
    BigInteger,
    Text,
    JSON,
    Float,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import JSON as JSONB
from sqlalchemy.orm import relationship
from ecoia.db.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supplier_id = Column(UUID(as_uuid=True), nullable=True)  # Making nullable as suppliers table might not exist yet
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    mime_type = Column(String(100))
    upload_status = Column(String(50), default="uploading")
    upload_progress = Column(Integer, default=0)
    file_path = Column(Text)
    status = Column(String(50), default="uploaded")  # uploaded, processing, processed, failed
    meta_data = Column(JSON, nullable=True)  # 'metadata' is reserved in SQLAlchemy
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UploadSession(Base):
    __tablename__ = "upload_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    status = Column(String(50), default="active")
    files_count = Column(Integer, default=0)
    total_size = Column(BigInteger, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    config = Column(JSONB, nullable=True)  # Store supplier configuration as JSONB
    is_active = Column(String(50), default="active")  # active, inactive
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProcessingStatus(Base):
    __tablename__ = "processing_status"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), nullable=False)
    job_id = Column(String(255), nullable=False, unique=True)  # Unique job identifier
    stage = Column(String(50), nullable=False)  # upload, parsing, ai_processing, export, completed, failed
    progress = Column(Integer, default=0)  # Progress percentage (0-100)
    message = Column(Text, nullable=True)  # Current status message
    error_details = Column(JSON, nullable=True)  # Error details if failed
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    meta_data = Column(JSON, nullable=True)  # Additional metadata


class Product(Base):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=True)
    name = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=True)
    category = Column(String(255), nullable=True)
    reference = Column(String(255), nullable=True)  # SKU
    brand = Column(String(255), nullable=True)
    status = Column(String(50), default="draft")  # draft, validated, rejected

    # Dynamic fields stored as JSON
    raw_data = Column(JSONB, nullable=True)  # Original extracted data
    processed_data = Column(JSONB, nullable=True)  # Processed/structured data

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    document = relationship("Document", backref="products")


class ProductScrapeResult(Base):
    __tablename__ = "product_scrape_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    source_url = Column(Text, nullable=False)
    source_site = Column(String(255), nullable=True)
    title = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    characteristics = Column(JSONB, nullable=True)
    images = Column(JSONB, nullable=True)
    raw_content = Column(Text, nullable=True)
    scraped_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", backref="scrape_results")


class ProductFormat(Base):
    __tablename__ = "product_formats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    yaml_content = Column(JSONB, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EnrichmentDocument(Base):
    __tablename__ = "enrichment_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    enrichment_type = Column(String(50), nullable=False, default="other")  # notice, catalogue, fiche_technique, other
    extracted_data = Column(JSONB, nullable=True)  # Structured data extracted from the document
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    match_confidence = Column(Float, nullable=True)  # AI matching confidence score
    match_method = Column(String(50), nullable=True)  # reference, ean, name_ai, manual
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    document = relationship("Document", backref="enrichment_documents")
    product = relationship("Product", backref="enrichment_documents")
