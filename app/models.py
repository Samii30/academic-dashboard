"""
Modèles ORM SQLAlchemy pour le suivi académique et le planning.
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class ModuleModel(Base):
    """
    Représente une Unité d'Enseignement / Matière (ex: Algorithmique, Systèmes).
    Table : modules
    """
    __tablename__ = "modules"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String(100), nullable=False)
    code = Column(String(20), nullable=False, unique=True, index=True)
    coefficient = Column(Float, nullable=False, default=1.0)

    # Relation avec les notes associées
    grades = relationship(
        "GradeModel",
        back_populates="module",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Module(code='{self.code}', nom='{self.nom}', coef={self.coefficient})>"


class GradeModel(Base):
    """
    Représente une note obtenue dans un module donné (ex: CC1, TP Noté, Partiel).
    Table : grades
    """
    __tablename__ = "grades"

    id = Column(Integer, primary_key=True, index=True)
    module_id = Column(
        Integer,
        ForeignKey("modules.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    note = Column(Float, nullable=False)
    coefficient = Column(Float, nullable=False, default=1.0)
    date = Column(String(10), nullable=False)  # Format ISO: AAAA-MM-JJ
    intitule = Column(String(150), nullable=False)

    # Relation avec le module parent
    module = relationship("ModuleModel", back_populates="grades")

    def __repr__(self) -> str:
        return f"<Grade(intitule='{self.intitule}', note={self.note}/20, module_id={self.module_id})>"


class TaskModel(Base):
    """
    Représente une tâche ou échéance du planning (ex: Rendre le DM d'Analyse).
    Table : tasks
    """
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    titre = Column(String(200), nullable=False)
    date_echeance = Column(String(10), nullable=True)  # Format ISO: AAAA-MM-JJ
    priorite = Column(String(20), nullable=False, default="Moyenne")  # Basse, Moyenne, Haute
    est_faite = Column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return f"<Task(titre='{self.titre}', priorite='{self.priorite}', est_faite={self.est_faite})>"


class CoursModel(Base):
    """
    Représente une séance de cours importée depuis un calendrier ICS (CM, TD, TP).
    Table : cours
    Ces séances ne sont PAS des tâches à faire, mais un planning de présence.
    """
    __tablename__ = "cours"

    id = Column(Integer, primary_key=True, index=True)
    summary_brut = Column(String(300), nullable=False)        # Résumé brut de l'événement ICS
    module_nom = Column(String(150), nullable=False)          # Nom propre du module (nettoyé)
    module_code = Column(String(30), nullable=False, index=True)  # Code UE normalisé
    type_cours = Column(String(20), nullable=False, default="COURS")  # CM, TD, TP, COURS
    date_cours = Column(String(10), nullable=True, index=True)  # Format ISO: AAAA-MM-JJ
    heure_debut = Column(String(5), nullable=True)            # Format HH:MM
    heure_fin = Column(String(5), nullable=True)              # Format HH:MM
    salle = Column(String(200), nullable=True)                # Salle / lieu
    groupe = Column(String(30), nullable=True)                # Groupe étudiant (ex: INFO2A)
    description = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Cours(module='{self.module_code}', date='{self.date_cours}', type='{self.type_cours}')>"
