from sqlalchemy import Column, String, Integer, DateTime, Text, BigInteger, Float, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
from pgvector.sqlalchemy import Vector
from datetime import datetime

Base = declarative_base()

class Fact(Base):
    __tablename__ = 'facts'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    entity_type = Column(String)
    entity_id = Column(String)
    attribute = Column(String)
    value = Column(Text)
    version = Column(String)
    valid_from = Column(DateTime, default=datetime.utcnow)
    valid_to = Column(DateTime, nullable=True)
    embedding = Column(Vector(384), nullable=True)   # for vector search

class Symbol(Base):
    __tablename__ = 'symbols'
    id = Column(BigInteger, primary_key=True)
    file = Column(String)
    name = Column(String)
    kind = Column(String)
    line = Column(Integer)
    version = Column(String)

class RequirementTraceability(Base):
    __tablename__ = 'requirement_traceability'
    id = Column(Integer, primary_key=True, autoincrement=True)
    requirement_id = Column(String, nullable=False, index=True)
    symbol_id = Column(String, nullable=False, index=True)
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, server_default=func.now())
    __table_args__ = (UniqueConstraint('requirement_id', 'symbol_id', name='uq_req_symbol'),)
