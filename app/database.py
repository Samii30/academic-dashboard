"""
Configuration de la base de données SQLite avec SQLAlchemy.
"""

from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Emplacement de la base SQLite à la racine du projet
BASE_DIR = Path(__file__).resolve().parent.parent
DB_FILE = BASE_DIR / "academic_dashboard.db"
DATABASE_URL = f"sqlite:///{DB_FILE}"

# Engine SQLite (check_same_thread=False requis pour FastAPI avec SQLite)
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

# Factory de sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Classe de base pour les modèles ORM
Base = declarative_base()


def get_db():
    """
    Générateur de session SQLAlchemy pour injection de dépendances FastAPI.
    Garantit la fermeture propre de la session après chaque requête.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialise la base de données et crée l'ensemble des tables (modules, grades, tasks)
    si elles n'existent pas encore.
    """
    # Import des modèles pour enregistrement dans le metadata de SQLAlchemy
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
