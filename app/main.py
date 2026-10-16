"""
Point d'entrée principal de l'application FastAPI.
Sert le frontend et expose l'ensemble des routes API REST (CRUD Modules, Notes, Tâches et Synthèse / Summary).
"""

from contextlib import asynccontextmanager
from datetime import date as dt_date
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Request, Depends, HTTPException, status, Query, File, Form, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import init_db, get_db, engine
from app.models import ModuleModel, GradeModel, TaskModel, CoursModel
from app.schemas import (
    HealthResponse,
    ModuleCreate,
    ModuleResponse,
    ModuleWithGradesResponse,
    GradeCreate,
    GradeResponse,
    TaskCreate,
    TaskUpdate,
    TaskResponse,
    SummaryResponse,
    ICSImportRequest,
    ICSImportResponse,
    CoursResponse,
)
from app.ics_parser import parse_ics, fetch_ics_from_url, normalize_key, make_code

# Chemins de base du projet
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise la base de données au lancement de l'application."""
    init_db()
    yield


# Initialisation de l'application FastAPI
app = FastAPI(
    title="Dashboard de Suivi Académique & Planning d'Études",
    description="API REST et Frontend pour le suivi des UE, des notes et du planning d'études.",
    version="2.1.0",
    lifespan=lifespan
)

# Montage des fichiers statiques et moteur de templates
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def compute_module_average(module: ModuleModel) -> Optional[float]:
    """
    Calcule la moyenne pondérée d'un module en fonction des notes et coefficients associés.
    Retourne None si le module n'a pas encore de note.
    """
    if not module.grades:
        return None
    total_points = sum(g.note * g.coefficient for g in module.grades)
    total_coefs = sum(g.coefficient for g in module.grades)
    if total_coefs <= 0:
        return None
    return round(total_points / total_coefs, 2)


# ==========================================
# Routes Frontend (HTML)
# ==========================================
@app.get("/", summary="Page d'accueil du Dashboard")
async def read_dashboard(request: Request):
    """Sert l'interface web principale."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"title": "Dashboard Académique | L1 Informatique"}
    )


# ==========================================
# Routes API : Santé & Synthèse (/api/summary)
# ==========================================
@app.get("/api/health", response_model=HealthResponse, summary="Santé de l'API")
async def health_check():
    """Vérifie la disponibilité de l'API et la connexion SQLite."""
    db_status = "connected"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {str(e)}"

    return HealthResponse(
        status="ok" if db_status == "connected" else "degraded",
        app="Dashboard de Suivi Académique & Planning d'Études",
        version="2.1.0",
        database=db_status
    )


@app.get("/api/summary", response_model=SummaryResponse, summary="Synthèse académique globale")
@app.get("/api/stats", response_model=SummaryResponse, summary="Alias de la synthèse académique")
def get_academic_summary(db: Session = Depends(get_db)):
    """
    Calcule la synthèse du tableau de bord :
    - Moyenne générale pondérée (par coefficients des modules)
    - Nombre total d'unités d'enseignement (UE)
    - Taux de réussite (% des modules avec moyenne >= 10/20)
    - Nombre de tâches en cours et prioritaires
    """
    modules = db.query(ModuleModel).all()
    tasks = db.query(TaskModel).all()

    total_modules = len(modules)
    graded_modules_count = 0
    modules_passed_count = 0

    weighted_sum = 0.0
    sum_module_coefs = 0.0

    for m in modules:
        avg = compute_module_average(m)
        if avg is not None:
            graded_modules_count += 1
            weighted_sum += avg * m.coefficient
            sum_module_coefs += m.coefficient
            if avg >= 10.0:
                modules_passed_count += 1

    general_average = None
    if sum_module_coefs > 0:
        general_average = round(weighted_sum / sum_module_coefs, 2)

    success_rate = None
    if graded_modules_count > 0:
        success_rate = round((modules_passed_count / graded_modules_count) * 100, 1)

    pending_tasks = sum(1 for t in tasks if not t.est_faite)
    high_priority_tasks = sum(1 for t in tasks if not t.est_faite and t.priorite == "Haute")

    return SummaryResponse(
        general_average=general_average,
        total_modules=total_modules,
        success_rate=success_rate,
        pending_tasks=pending_tasks,
        high_priority_tasks=high_priority_tasks
    )


# ==========================================
# Routes API : Modules (GET, POST, DELETE)
# ==========================================
@app.get("/api/modules", response_model=List[ModuleWithGradesResponse], summary="Lister les modules")
def get_modules(db: Session = Depends(get_db)):
    """Récupère tous les modules avec leurs notes et leur moyenne calculée."""
    modules = db.query(ModuleModel).order_by(ModuleModel.code.asc()).all()
    result = []
    for m in modules:
        avg = compute_module_average(m)
        result.append(
            ModuleWithGradesResponse(
                id=m.id,
                nom=m.nom,
                code=m.code,
                coefficient=m.coefficient,
                grades=[GradeResponse.model_validate(g) for g in m.grades],
                average=avg
            )
        )
    return result


@app.post("/api/modules", response_model=ModuleResponse, status_code=status.HTTP_201_CREATED, summary="Créer un module")
def create_module(module_in: ModuleCreate, db: Session = Depends(get_db)):
    """Crée une nouvelle Unité d'Enseignement (UE)."""
    clean_code = module_in.code.strip().upper()
    existing = db.query(ModuleModel).filter(ModuleModel.code == clean_code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Le code UE '{clean_code}' existe déjà."
        )

    db_module = ModuleModel(
        nom=module_in.nom.strip(),
        code=clean_code,
        coefficient=module_in.coefficient
    )
    db.add(db_module)
    db.commit()
    db.refresh(db_module)
    return db_module


@app.delete("/api/modules/{module_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Supprimer un module")
def delete_module(module_id: int, db: Session = Depends(get_db)):
    """Supprime un module et toutes ses notes associées en cascade."""
    module = db.query(ModuleModel).filter(ModuleModel.id == module_id).first()
    if not module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module introuvable.")

    db.delete(module)
    db.commit()
    return None


# ==========================================
# Routes API : Notes / Grades (GET, POST, DELETE)
# ==========================================
@app.get("/api/grades", response_model=List[GradeResponse], summary="Lister les notes")
def get_grades(module_id: Optional[int] = Query(None, description="Filtre par identifiant de module"), db: Session = Depends(get_db)):
    """Lister l'ensemble des notes enregistrées (avec filtre optionnel par module)."""
    query = db.query(GradeModel)
    if module_id is not None:
        query = query.filter(GradeModel.module_id == module_id)
    return query.order_by(GradeModel.date.desc(), GradeModel.id.desc()).all()


@app.post("/api/grades", response_model=GradeResponse, status_code=status.HTTP_201_CREATED, summary="Ajouter une note")
def create_grade(grade_in: GradeCreate, db: Session = Depends(get_db)):
    """Ajoute une évaluation notée à un module spécifique."""
    module = db.query(ModuleModel).filter(ModuleModel.id == grade_in.module_id).first()
    if not module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module ID {grade_in.module_id} introuvable."
        )

    grade_date = grade_in.date.strip() if grade_in.date and grade_in.date.strip() else dt_date.today().isoformat()

    db_grade = GradeModel(
        module_id=grade_in.module_id,
        note=grade_in.note,
        coefficient=grade_in.coefficient,
        date=grade_date,
        intitule=grade_in.intitule.strip()
    )
    db.add(db_grade)
    db.commit()
    db.refresh(db_grade)
    return db_grade


@app.delete("/api/grades/{grade_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Supprimer une note")
def delete_grade(grade_id: int, db: Session = Depends(get_db)):
    """Supprime une note spécifique."""
    grade = db.query(GradeModel).filter(GradeModel.id == grade_id).first()
    if not grade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note introuvable.")

    db.delete(grade)
    db.commit()
    return None


# ==========================================
# Routes API : Tâches (GET, POST, PATCH, DELETE)
# ==========================================
@app.get("/api/tasks", response_model=List[TaskResponse], summary="Lister les tâches")
def get_tasks(db: Session = Depends(get_db)):
    """Récupère l'ensemble des tâches du planning."""
    tasks = db.query(TaskModel).order_by(
        TaskModel.est_faite.asc(),
        TaskModel.date_echeance.asc()
    ).all()
    return tasks


@app.post("/api/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED, summary="Créer une tâche")
def create_task(task_in: TaskCreate, db: Session = Depends(get_db)):
    """Crée une nouvelle tâche dans le planning."""
    db_task = TaskModel(
        titre=task_in.titre.strip(),
        date_echeance=task_in.date_echeance.strip() if task_in.date_echeance else None,
        priorite=task_in.priorite,
        est_faite=task_in.est_faite
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


@app.put("/api/tasks/{task_id}", response_model=TaskResponse, summary="Modifier complètement une tâche")
def replace_task(task_id: int, task_in: TaskUpdate, db: Session = Depends(get_db)):
    """Met à jour les informations d'une tâche existante (titre, date, priorité)."""
    task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tâche introuvable.")

    if task_in.titre is not None:
        task.titre = task_in.titre.strip()
    if task_in.date_echeance is not None:
        task.date_echeance = task_in.date_echeance.strip() if task_in.date_echeance else None
    if task_in.priorite is not None:
        task.priorite = task_in.priorite
    if task_in.est_faite is not None:
        task.est_faite = task_in.est_faite

    db.commit()
    db.refresh(task)
    return task


@app.patch("/api/tasks/{task_id}", response_model=TaskResponse, summary="Basculer ou modifier une tâche")
def update_task(task_id: int, task_in: TaskUpdate, db: Session = Depends(get_db)):
    """Bascule l'état fait/non fait ou modifie les informations d'une tâche."""
    task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tâche introuvable.")

    if task_in.titre is not None:
        task.titre = task_in.titre.strip()
    if task_in.date_echeance is not None:
        task.date_echeance = task_in.date_echeance.strip() if task_in.date_echeance else None
    if task_in.priorite is not None:
        task.priorite = task_in.priorite
    if task_in.est_faite is not None:
        task.est_faite = task_in.est_faite

    db.commit()
    db.refresh(task)
    return task


@app.delete("/api/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Supprimer une tâche")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    """Supprime une tâche du planning."""
    task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tâche introuvable.")

    db.delete(task)
    db.commit()
    return None


@app.delete("/api/tasks", summary="Vider les tâches du planning")
def clear_tasks(completed_only: bool = Query(False, description="Supprimer uniquement les tâches terminées"), db: Session = Depends(get_db)):
    """Vide toutes les tâches ou uniquement les tâches terminées pour nettoyer le planning."""
    query = db.query(TaskModel)
    if completed_only:
        deleted_count = query.filter(TaskModel.est_faite == True).delete()
    else:
        deleted_count = query.delete()
    db.commit()
    return {"message": f"{deleted_count} tâche(s) supprimée(s).", "deleted_count": deleted_count}


# ==========================================
# Routes API : Calendrier de Cours (Séances)
# ==========================================
@app.get("/api/cours", response_model=List[CoursResponse], summary="Lister les séances de cours")
def get_cours(
    semaine: Optional[str] = Query(None, description="Semaine au format AAAA-Www (ex: 2024-W42)"),
    date_debut: Optional[str] = Query(None, description="Date début filtrage (AAAA-MM-JJ)"),
    date_fin: Optional[str] = Query(None, description="Date fin filtrage (AAAA-MM-JJ)"),
    module_code: Optional[str] = Query(None, description="Filtrer par code module"),
    db: Session = Depends(get_db)
):
    """Récupère les séances de cours du calendrier (importées via ICS), avec filtres optionnels."""
    from datetime import datetime, timedelta
    import re as _re

    query = db.query(CoursModel)

    if semaine:
        # Parse format ISO week: AAAA-Www
        m = _re.match(r'(\d{4})-W(\d{2})', semaine)
        if m:
            year, week = int(m.group(1)), int(m.group(2))
            # Lundi de la semaine
            monday = datetime.strptime(f"{year}-W{week:02d}-1", "%Y-W%W-%w").date()
            sunday = monday + timedelta(days=6)
            query = query.filter(
                CoursModel.date_cours >= monday.isoformat(),
                CoursModel.date_cours <= sunday.isoformat()
            )
    else:
        if date_debut:
            query = query.filter(CoursModel.date_cours >= date_debut)
        if date_fin:
            query = query.filter(CoursModel.date_cours <= date_fin)

    if module_code:
        query = query.filter(CoursModel.module_code == module_code.upper())

    return query.order_by(CoursModel.date_cours.asc(), CoursModel.heure_debut.asc()).all()


@app.delete("/api/cours", summary="Vider le calendrier de cours")
def clear_cours(db: Session = Depends(get_db)):
    """Supprime toutes les séances de cours (pour réimporter proprement)."""
    deleted_count = db.query(CoursModel).delete()
    db.commit()
    return {"message": f"{deleted_count} séance(s) supprimée(s).", "deleted_count": deleted_count}



@app.post("/api/import-ics", response_model=ICSImportResponse, summary="Importer un planning universitaire ICS")
async def import_ics_calendar(
    request: Request,
    file: Optional[UploadFile] = File(None),
    group_filter: Optional[str] = Form(None, description="Groupe à filtrer (ex: INFO2A)"),
    ics_url: Optional[str] = Form(None, description="URL iCal à télécharger"),
    db: Session = Depends(get_db)
):
    """
    Importe un planning iCalendar depuis un fichier .ics ou une URL.
    - Filtre optionnellement par groupe étudiant (ex: INFO2A).
    - Les évaluations (examens, partiels, CC…) → table tasks (priorité Haute).
    - Les cours normaux (CM, TD, TP) → table cours (calendrier de séances).
    - Supporte l'expansion des RRULE pour les cours récurrents.
    """
    raw_content = ""
    content_type = request.headers.get("content-type", "")

    # 1. Fichier uploadé via multipart/form-data
    if file is not None and file.filename:
        try:
            content_bytes = await file.read()
            try:
                raw_content = content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                raw_content = content_bytes.decode("latin-1")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Erreur de lecture du fichier uploadé : {str(e)}"
            )

    # 2. URL transmise dans le formulaire
    elif ics_url and ics_url.strip():
        try:
            raw_content = fetch_ics_from_url(ics_url.strip())
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Erreur lors du téléchargement de l'URL ICS : {str(e)}"
            )

    # 3. Payload JSON (compatibilité ancienne API)
    elif "application/json" in content_type:
        try:
            body = await request.json()
            if body.get("ics_url"):
                raw_content = fetch_ics_from_url(body["ics_url"].strip())
            elif body.get("ics_content"):
                raw_content = body["ics_content"].strip()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Requête JSON invalide : {str(e)}"
            )

    if not raw_content or not raw_content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Veuillez fournir un fichier .ics ou une URL de calendrier iCal valide."
        )

    # ── Analyse du calendrier ───────────────────────────────────────────────
    gf = (group_filter or "").strip()
    try:
        parsed = parse_ics(raw_content, group_filter=gf)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erreur lors de l'analyse du format iCalendar : {str(e)}"
        )

    if not parsed["cours"]:
        msg = "Aucun événement valide détecté"
        if gf:
            msg += f" pour le groupe « {gf} »"
        return ICSImportResponse(
            modules_created=0, modules_existing=0,
            tasks_created=0, tasks_skipped=0, cours_created=0,
            message=msg + " dans le flux iCalendar."
        )

    # ── 1. Modules : un seul par matière (clé = nom normalisé) ──────────────
    db_modules = db.query(ModuleModel).all()
    by_key = {normalize_key(m.nom): m for m in db_modules}
    taken_codes = {m.code for m in db_modules}
    code_map = {}          # code généré par le parseur -> code réel en base
    nom_map = {}           # idem pour le nom
    modules_created = 0
    modules_existing = 0

    for mod in parsed["modules"]:
        existing = by_key.get(mod["key"])
        if existing:
            modules_existing += 1
            code_map[mod["code"]] = existing.code
            nom_map[mod["code"]] = existing.nom
            continue
        code = mod["code"] if mod["code"] not in taken_codes else make_code(mod["nom"], taken_codes)
        taken_codes.add(code)
        db.add(ModuleModel(nom=mod["nom"][:100], code=code, coefficient=1.0))
        by_key[mod["key"]] = None  # évite toute recréation dans la même passe
        code_map[mod["code"]] = code
        nom_map[mod["code"]] = mod["nom"]
        modules_created += 1
    db.commit()

    # ── 2. Séances (CM/TD/TP/Tutorat/évaluations) → table cours, sans doublon ──
    def ckey(code, typ, nom, d, h1, h2):
        return (code, typ, nom, d, h1, h2)

    seen = {
        ckey(c.module_code, c.type_cours, c.module_nom, c.date_cours, c.heure_debut, c.heure_fin)
        for c in db.query(CoursModel).all()
    }
    cours_created = 0
    for c in parsed["cours"]:
        code = code_map.get(c["module_code"], c["module_code"])
        nom = c["module_nom"] if c["type_cours"] in ("EXAM", "TUTORAT") else nom_map.get(c["module_code"], c["module_nom"])
        k = ckey(code, c["type_cours"], nom, c["date_iso"], c["heure_debut"], c["heure_fin"])
        if k in seen:
            continue
        seen.add(k)
        db.add(CoursModel(
            summary_brut=c["summary"], module_nom=nom[:150], module_code=code,
            type_cours=c["type_cours"], date_cours=c["date_iso"],
            heure_debut=c["heure_debut"], heure_fin=c["heure_fin"],
            salle=(c["salle"] or None), groupe=c["groupe"] or gf or None,
            description=c["description"],
        ))
        cours_created += 1

    # ── 3. Évaluations (CC, DS, examen, TP noté…) → tâches uniquement ─────────
    existing_tasks = {(t.titre, t.date_echeance) for t in db.query(TaskModel).all()}
    tasks_created = 0
    tasks_skipped = 0
    for ev in parsed["evals"]:
        titre = f"📝 {ev['titre']}"[:200]
        if (titre, ev["date_iso"]) in existing_tasks:
            tasks_skipped += 1
            continue
        existing_tasks.add((titre, ev["date_iso"]))
        db.add(TaskModel(titre=titre, date_echeance=ev["date_iso"], priorite="Haute", est_faite=False))
        tasks_created += 1
    db.commit()

    st = parsed["stats"]
    filter_info = f" (groupe « {gf} »)" if gf else ""
    message = (
        f"Importation terminée{filter_info} : {modules_created} module(s) créé(s) "
        f"({modules_existing} déjà présent(s)), {cours_created} séance(s) au calendrier, "
        f"{tasks_created} évaluation(s) ajoutée(s) aux tâches"
        f" ({tasks_skipped} déjà présente(s)). "
        f"Ignorés : {st['ignores_groupe']} autre(s) groupe(s), {st['ignores_annules']} annulé(s)."
    )
    return ICSImportResponse(
        modules_created=modules_created, modules_existing=modules_existing,
        tasks_created=tasks_created, tasks_skipped=tasks_skipped,
        cours_created=cours_created, message=message,
    )


@app.delete("/api/planning", summary="Réinitialiser le planning importé")
def reset_imported_planning(db: Session = Depends(get_db)):
    """
    Repart de zéro après un import raté : supprime toutes les séances, les tâches issues
    d'un import (📝 … ou ancien format « [CODE] … ») et les modules SANS note.
    Les modules ayant des notes et les tâches créées à la main sont conservés.
    """
    n_cours = db.query(CoursModel).delete()
    n_tasks = db.query(TaskModel).filter(
        (TaskModel.titre.like("📝%")) | (TaskModel.titre.like("[%] %"))
    ).delete(synchronize_session=False)
    n_mods = 0
    for m in db.query(ModuleModel).all():
        if not m.grades:
            db.delete(m)
            n_mods += 1
    db.commit()
    return {
        "message": f"Planning réinitialisé : {n_cours} séance(s), {n_tasks} tâche(s) importée(s) et {n_mods} module(s) sans note supprimés.",
        "cours": n_cours, "tasks": n_tasks, "modules": n_mods,
    }
