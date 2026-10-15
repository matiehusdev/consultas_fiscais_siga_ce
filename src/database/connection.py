from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from src.config import settings
from src.database.models import Base

# Ativação obrigatória de chaves estrangeiras e modo WAL no SQLite
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()

db_url = f"sqlite:///{settings.database_path.as_posix()}"

engine = create_engine(
    db_url,
    connect_args={"check_same_thread": False},
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Cria todas as tabelas no banco de dados se não existirem e aplica migrações leves."""
    settings.ensure_directories()
    Base.metadata.create_all(bind=engine)

    # Migração leve para bancos já criados: garante adição das novas colunas de certificado
    try:
        with engine.connect() as conn:
            cursor = conn.connection.cursor()
            cursor.execute("PRAGMA table_info(empresas)")
            cols = [row[1] for row in cursor.fetchall()]
            new_columns = [
                ("certificado_caminho", "VARCHAR(500)"),
                ("certificado_senha_hash", "VARCHAR(500)"),
                ("certificado_nome", "VARCHAR(255)"),
                ("certificado_validade", "DATETIME"),
                ("certificado_cn", "VARCHAR(255)")
            ]
            for col_name, col_type in new_columns:
                if col_name not in cols:
                    cursor.execute(f"ALTER TABLE empresas ADD COLUMN {col_name} {col_type}")
            conn.commit()
    except Exception:
        pass

def get_db():
    """Dependency para FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@contextmanager
def get_db_context():
    """Context manager para uso fora de endpoints FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
