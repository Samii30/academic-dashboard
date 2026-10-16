"""
Schémas Pydantic pour la validation et la sérialisation des données de l'API.
"""

from datetime import date as dt_date
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


# ==========================================
# Schémas pour les Notes (Grades)
# ==========================================
class GradeBase(BaseModel):
    module_id: int = Field(..., description="Identifiant du module associé")
    note: float = Field(..., ge=0, le=20, description="Note sur 20")
    coefficient: float = Field(default=1.0, gt=0, description="Coefficient de l'évaluation")
    date: Optional[str] = Field(default=None, description="Date de l'évaluation (AAAA-MM-JJ)")
    intitule: str = Field(..., min_length=1, max_length=150, description="Intitulé (ex: DS1, TP Noté)")


class GradeCreate(GradeBase):
    pass


class GradeResponse(BaseModel):
    id: int
    module_id: int
    note: float
    coefficient: float
    date: str
    intitule: str

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Schémas pour les Modules
# ==========================================
class ModuleBase(BaseModel):
    nom: str = Field(..., min_length=2, max_length=100, description="Nom complet du module")
    code: str = Field(..., min_length=2, max_length=20, description="Code unique de l'UE (ex: INF101)")
    coefficient: float = Field(default=1.0, gt=0, description="Coefficient de l'UE")


class ModuleCreate(ModuleBase):
    pass


class ModuleResponse(ModuleBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class ModuleWithGradesResponse(ModuleBase):
    id: int
    grades: List[GradeResponse] = []
    average: Optional[float] = Field(None, description="Moyenne calculée pour ce module (/20)")

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Schémas pour les Tâches (Tasks / Planning)
# ==========================================
class TaskBase(BaseModel):
    titre: str = Field(..., min_length=2, max_length=200, description="Intitulé de la tâche")
    date_echeance: Optional[str] = Field(None, description="Date limite (AAAA-MM-JJ)")
    priorite: str = Field(default="Moyenne", description="Priorité : Basse, Moyenne, Haute")
    est_faite: bool = Field(default=False, description="Indicateur d'achèvement")


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    titre: Optional[str] = Field(None, min_length=2, max_length=200)
    date_echeance: Optional[str] = None
    priorite: Optional[str] = None
    est_faite: Optional[bool] = None


class TaskResponse(TaskBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Schémas Statistiques & Synthèse / Summary
# ==========================================
class SummaryResponse(BaseModel):
    general_average: Optional[float] = Field(None, description="Moyenne générale pondérée (/20)")
    total_modules: int = Field(default=0, description="Nombre total d'unités d'enseignement")
    success_rate: Optional[float] = Field(None, description="Taux de réussite (% des modules avec moyenne >= 10/20)")
    pending_tasks: int = Field(default=0, description="Nombre de tâches en cours")
    high_priority_tasks: int = Field(default=0, description="Nombre de tâches prioritaires non faites")


# Alias de compatibilité
StatsResponse = SummaryResponse


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    database: str


# ==========================================
# Schémas Import ICS / iCal
# ==========================================
class ICSImportRequest(BaseModel):
    ics_url: Optional[str] = Field(None, description="URL publique du calendrier iCal (ADE, Moodle, ENT)")
    ics_content: Optional[str] = Field(None, description="Contenu texte brut du fichier .ics")


class ICSImportResponse(BaseModel):
    modules_created: int = Field(default=0, description="Nombre de nouveaux modules créés")
    modules_existing: int = Field(default=0, description="Nombre de modules déjà existants")
    tasks_created: int = Field(default=0, description="Nombre de nouvelles tâches ou examens ajoutés")
    tasks_skipped: int = Field(default=0, description="Nombre de tâches ignorées (doublons ou filtrées)")
    cours_created: int = Field(default=0, description="Nombre de séances de cours ajoutées au calendrier")
    message: str = Field(..., description="Message récapitulatif")


# ==========================================
# Schémas Cours / Calendrier de séances
# ==========================================
class CoursResponse(BaseModel):
    id: int
    summary_brut: str
    module_nom: str
    module_code: str
    type_cours: str
    date_cours: Optional[str] = None
    heure_debut: Optional[str] = None
    heure_fin: Optional[str] = None
    salle: Optional[str] = None
    groupe: Optional[str] = None
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
