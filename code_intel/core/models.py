import json
from sqlalchemy import Column, String, Integer, DateTime, Text, BigInteger, Float, UniqueConstraint, Boolean, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base, relationship
from pgvector.sqlalchemy import Vector
from datetime import datetime
from sqlalchemy.types import TypeDecorator
from code_intel.settings import DATABASE_URL

# Check if database URL indicates SQLite
if "sqlite" in DATABASE_URL:
    from sqlalchemy.ext.compiler import compiles
    from sqlalchemy.types import BigInteger

    @compiles(BigInteger, "sqlite")
    def compile_big_int_sqlite(type_, compiler, **kw):
        return "INTEGER"

    class SQLiteArray(TypeDecorator):
        impl = Text
        cache_ok = True

        def __init__(self, item_type=None, *args, **kwargs):
            self.item_type = item_type
            super().__init__(*args, **kwargs)

        def process_bind_param(self, value, dialect):
            if value is not None:
                return json.dumps(value)
            return None

        def process_result_value(self, value, dialect):
            if value is not None:
                try:
                    return json.loads(value)
                except Exception:
                    return []
            return None

    def ARRAY(item_type, *args, **kwargs):
        return SQLiteArray(item_type, *args, **kwargs)
else:
    from sqlalchemy import ARRAY

Base = declarative_base()

class Fact(Base):
    __tablename__ = 'facts'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    entity_type = Column(String)
    entity_id = Column(String)
    attribute = Column(String)
    value = Column(Text)
    version = Column(String)
    extractor_version = Column(String, index=True)
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

class DerivedFact(Base):
    __tablename__ = 'derived_facts'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    fact_type = Column(String, index=True)  # e.g., 'transitive_calls'
    entity_id = Column(String, index=True, nullable=True) # e.g., symbol FQN for impact
    value = Column(Text)
    version = Column(String, index=True)
    extractor_version = Column(String, index=True)
    depends_on = Column(ARRAY(BigInteger))
    depends_on_derived = Column(ARRAY(BigInteger))
    is_stale = Column(Boolean, default=False)
    last_validated = Column(DateTime, server_default=func.now(), onupdate=func.now())

class VersionMetadata(Base):
    __tablename__ = 'version_metadata'
    key = Column(String, primary_key=True)
    value = Column(String)

class GraphNode(Base):
    """Read Model: Optimized for traversal"""
    __tablename__ = 'graph_nodes'
    id = Column(BigInteger, primary_key=True)
    fqn = Column(String, index=True)
    kind = Column(String)
    file = Column(String)
    version = Column(String, index=True)
    introduced_in = Column(String)
    deleted_in = Column(String, nullable=True)
    valid_from_sha = Column(String, nullable=True, index=True)
    valid_to_sha = Column(String, nullable=True, index=True)

class GraphEdge(Base):
    """Read Model: Optimized for traversal"""
    __tablename__ = 'graph_edges'
    id = Column(BigInteger, primary_key=True)
    from_fqn = Column(String, index=True)
    to_fqn = Column(String, index=True)
    edge_type = Column(String, index=True)
    version = Column(String, index=True)
    confidence = Column(Float)
    introduced_in = Column(String)
    deleted_in = Column(String, nullable=True)
    valid_from_sha = Column(String, nullable=True, index=True)
    valid_to_sha = Column(String, nullable=True, index=True)

class LLMArtifact(Base):
    __tablename__ = 'llm_artifacts'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    artifact_type = Column(String, index=True) # e.g., 'requirement', 'summary'
    entity_id = Column(String, index=True, nullable=True) # e.g., if specific to a symbol
    value = Column(Text)
    version = Column(String, index=True)
    grounded_in = Column(ARRAY(BigInteger))
    generation_prompt = Column(Text)
    model_version = Column(String)
    is_verified = Column(Boolean, default=True)
    confidence = Column(Float, default=1.0)
    timestamp = Column(DateTime, server_default=func.now())

class ModuleAnalysis(Base):
    __tablename__ = 'module_analyses'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    module_path = Column(String, index=True, nullable=False)
    status = Column(String(50), nullable=False, default='DRAFT')
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    versions = relationship("AnalysisVersion", back_populates="module_analysis", cascade="all, delete-orphan")

class AnalysisVersion(Base):
    __tablename__ = 'analysis_versions'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    module_analysis_id = Column(BigInteger, ForeignKey('module_analyses.id', ondelete='CASCADE'), nullable=False)
    git_commit_sha = Column(String(40), index=True, nullable=False)
    version_num = Column(Integer, nullable=False)
    business_rules = Column(JSON, nullable=True)
    edge_cases = Column(JSON, nullable=True)
    data_transformations = Column(JSON, nullable=True)
    side_effects = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    module_analysis = relationship("ModuleAnalysis", back_populates="versions")
