"""
Parseur de calendriers universitaires iCalendar (.ics) — version 3.

Principes :
  * Parseur RFC 5545 en Python pur (aucune dépendance obligatoire ; python-dateutil
    est utilisé s'il est présent pour les RRULE, sinon un repli manuel prend le relais).
  * Un module est identifié par son NOM NORMALISÉ (sans accents, sans CM/TD/TP,
    sans groupe, avec alias « Introduction à la prog en C » = « Intro à la programmation en C »),
    jamais par un code deviné dans le texte → plus de doublons ni de faux modules.
  * Les évaluations (CC1, DS, Examen, Partiel, TP noté, Projet, Rendu…) ne créent
    JAMAIS de module : elles deviennent des tâches (et apparaissent aussi dans l'emploi du temps).
  * Filtrage de groupe fiable : un événement sans groupe précisé (ex. « (INFO) ») est
    conservé pour tout le monde ; « INFO 2AB » est conservé pour INFO 2A et INFO 2B ;
    « INFO 2A » est exclu pour INFO 2B.
"""

from __future__ import annotations

import re
import unicodedata
import urllib.request
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

try:  # facultatif
    from dateutil.rrule import rrulestr
    HAS_DATEUTIL = True
except Exception:  # pragma: no cover
    HAS_DATEUTIL = False

try:
    from zoneinfo import ZoneInfo
    _PARIS = ZoneInfo("Europe/Paris")
    _UTC = ZoneInfo("UTC")
except Exception:  # pragma: no cover
    _PARIS = _UTC = None

MAX_OCCURRENCES = 400          # garde-fou RRULE
DEFAULT_HORIZON_DAYS = 220     # un semestre complet + marge si la RRULE n'a pas de fin

# ---------------------------------------------------------------------------
# Regex
# ---------------------------------------------------------------------------

CANCELLED_RE = re.compile(r"\b(supprim[ée]e?|annul[ée]e?)\b", re.IGNORECASE)

# Évaluation : on ne regarde QUE le titre (pas la description, qui contient « Groupe TP… »).
EVAL_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:"
    r"cc\s*\d*|ds\s*\d*|ct\s*\d*|"
    r"examens?|partiels?|rattrapage|contr[oô]les?|soutenances?|"
    r"projets?|rendus?|livrables?|[ée]valuations?|oral|quiz|"
    r"(?:tp|td)\s+not[ée]e?s?"
    r")(?![A-Za-z0-9])",
    re.IGNORECASE,
)

PREFIX_RE = re.compile(r"^\s*(cm|td|tp)\b\s*[-:/]?\s*", re.IGNORECASE)
PAREN_RE = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]")
EVAL_TIME_NOTE_RE = re.compile(
    r"(\b\d+\s*h\b.*$)|(\b(?:1/3|tiers)[\s-]*temps\b)", re.IGNORECASE
)
EVAL_LABEL_RE = re.compile(
    r"^\s*(?:(?:cc|ds|ct)\s*\d*|examens?|partiels?|contr[oô]les?|rattrapage|"
    r"(?:tp|td)\s+not[ée]e?s?|soutenances?|rendus?|projets?|livrables?)\b[\s:\-–]*"
    r"(?:(?:rattrapage|not[ée]e?s?)\b[\s:\-–]*)?",
    re.IGNORECASE,
)

TUTORAT_RE = re.compile(r"^\s*tutorat\b", re.IGNORECASE)
GROUP_TOKEN_RE = re.compile(r"INFO\s*[-_ ]?(\d)\s*([A-Z]{1,4})\b", re.IGNORECASE)

_STOP = {"et", "a", "la", "le", "les", "au", "aux", "en", "de", "des", "du", "d", "l", "un", "une"}
_ALIAS = {
    "introduction": "intro", "programmation": "prog", "developpement": "dev",
    "technologies": "techno", "technologie": "techno", "mathematiques": "maths",
    "mathematique": "maths", "generales": "general", "generale": "general",
}
_SMALL = {"et", "à", "la", "le", "les", "au", "aux", "en", "de", "des", "du", "d'", "l'", "un", "une"}


# ---------------------------------------------------------------------------
# Utilitaires texte
# ---------------------------------------------------------------------------

def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _unescape(v: str) -> str:
    out, i = [], 0
    while i < len(v):
        c = v[i]
        if c == "\\" and i + 1 < len(v):
            n = v[i + 1]
            out.append("\n" if n in "nN" else n)
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def normalize_key(name: str) -> str:
    """Clé canonique d'un module : « Introduction à la prog en C » == « Intro à la programmation en C »."""
    s = _strip_accents(name).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    toks = []
    for t in s.split():
        if t in _STOP:
            continue
        t = _ALIAS.get(t, t)
        if len(t) > 3 and t.endswith("s"):
            t = t[:-1]
        toks.append(t)
    return " ".join(toks)


def smart_title(name: str) -> str:
    words = re.split(r"(\s+)", name.strip())
    out, first = [], True
    for w in words:
        if not w or w.isspace():
            out.append(w)
            continue
        if not first and w.lower() in _SMALL:
            out.append(w.lower())
        else:
            out.append(w[0].upper() + w[1:])
        first = False
    return "".join(out)


def clean_summary(summary: str) -> str:
    """« TD Mathématiques générales (INFO 2AB) » → « Mathématiques Générales »."""
    s = PREFIX_RE.sub("", summary)
    s = PAREN_RE.sub("", s)
    s = re.sub(r"\s+", " ", s).strip(" -:/–")
    return smart_title(s) if s else summary.strip()


def clean_eval_title(summary: str) -> str:
    """« CC1 Méthodo et intro au développement (INFO) (1h + 20 min 1/3 temps) » → « CC1 Méthodo et Intro au Développement »."""
    s = PAREN_RE.sub("", summary)
    s = EVAL_TIME_NOTE_RE.sub("", s)
    s = re.sub(r"\s+", " ", s).strip(" -:/–+")
    return s or summary.strip()


def eval_target_name(summary: str) -> str:
    """Nom de la matière visée par une évaluation (« CC2 Algèbre 1 » → « Algèbre 1 »)."""
    s = clean_eval_title(summary)
    s = EVAL_LABEL_RE.sub("", s)
    return s.strip(" -:/–+")


def detect_type(summary: str) -> str:
    m = re.match(r"\s*(cm|td|tp)\b", summary, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    if TUTORAT_RE.match(summary):
        return "TUTORAT"
    return "COURS"


def make_code(name: str, taken: set) -> str:
    """Code court lisible : « Algèbre 1 » → ALG1, « Technologies Web 1 » → TW1, « Anglais » → ANG."""
    words = [w for w in re.split(r"[^A-Za-z0-9]+", _strip_accents(name)) if w and w.lower() not in _STOP]
    digits = ""
    if words and words[-1].isdigit():
        digits = words.pop()
    letters = [w for w in words if not w.isdigit()]
    if not letters:
        base = "UE"
    elif len(letters) == 1:
        base = letters[0][:3].upper()
    else:
        base = "".join(w[0] for w in letters)[:5].upper()
    code = base + digits
    final, n = code, 2
    while final in taken:
        final = f"{code}{n}"
        n += 1
    taken.add(final)
    return final


# ---------------------------------------------------------------------------
# Groupes
# ---------------------------------------------------------------------------

def _group_tokens(text: str) -> List[Tuple[str, set]]:
    return [(m.group(1), set(m.group(2).upper())) for m in GROUP_TOKEN_RE.finditer(text)]


def group_matches(summary: str, group_filter: str) -> bool:
    """
    True si l'événement concerne le groupe de l'étudiant.
      - pas de filtre            → tout est gardé
      - aucun groupe dans le titre (ex. « (INFO) », « Tutorat… ») → gardé (événement commun)
      - « INFO 2AB » → gardé pour 2A et 2B ; « INFO 2A » → refusé pour 2B
    """
    gf = (group_filter or "").strip()
    if not gf:
        return True
    ev = _group_tokens(summary)
    if not ev:
        return True
    mine = _group_tokens(gf)
    if not mine:  # filtre libre (ex. « L1-INFO-A ») : simple recherche de sous-chaîne
        return re.sub(r"\W+", "", gf).upper() in re.sub(r"\W+", "", summary).upper()
    for year, letters in mine:
        for ey, eletters in ev:
            if year == ey and letters <= eletters:
                return True
    return False


# ---------------------------------------------------------------------------
# Lecture RFC 5545
# ---------------------------------------------------------------------------

def _unfold(raw: str) -> List[str]:
    lines: List[str] = []
    for line in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line[:1] in (" ", "\t") and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    return lines


def _split_prop(line: str) -> Optional[Tuple[str, Dict[str, str], str]]:
    in_q, idx = False, -1
    for i, ch in enumerate(line):
        if ch == '"':
            in_q = not in_q
        elif ch == ":" and not in_q:
            idx = i
            break
    if idx < 0:
        return None
    head, value = line[:idx], line[idx + 1:]
    parts = re.split(r";(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)", head)
    name, params = parts[0].upper(), {}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            params[k.upper()] = v.strip('"')
    return name, params, value


def _parse_dt(value: str, params: Dict[str, str]) -> Optional[datetime]:
    v = value.strip()
    m = re.match(r"^(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2})(\d{2})?(Z)?)?$", v)
    if not m:
        return None
    y, mo, d, hh, mi, ss, z = m.groups()
    dt = datetime(int(y), int(mo), int(d), int(hh or 0), int(mi or 0), int(ss or 0))
    if z and _PARIS is not None:
        dt = dt.replace(tzinfo=_UTC).astimezone(_PARIS).replace(tzinfo=None)
    return dt


def _read_events(raw: str) -> List[Dict[str, Any]]:
    events, cur, depth = [], None, 0
    for line in _unfold(raw):
        if not line.strip():
            continue
        u = line.strip().upper()
        if u == "BEGIN:VEVENT":
            cur, depth = {"exdates": []}, 0
            continue
        if cur is None:
            continue
        if u.startswith("BEGIN:"):          # VALARM, etc.
            depth += 1
            continue
        if u == "END:VEVENT":
            events.append(cur)
            cur = None
            continue
        if u.startswith("END:"):
            depth = max(0, depth - 1)
            continue
        if depth:
            continue
        prop = _split_prop(line)
        if not prop:
            continue
        name, params, value = prop
        if name == "SUMMARY":
            cur["summary"] = _unescape(value).strip()
        elif name == "DESCRIPTION":
            cur["description"] = _unescape(value).strip()
        elif name == "LOCATION":
            cur["location"] = _unescape(value).strip()
        elif name == "STATUS":
            cur["status"] = value.strip().upper()
        elif name == "DTSTART":
            cur["start"] = _parse_dt(value, params)
            cur["all_day"] = "T" not in value
        elif name == "DTEND":
            cur["end"] = _parse_dt(value, params)
        elif name == "RRULE":
            cur["rrule"] = value.strip()
        elif name == "EXDATE":
            for part in value.split(","):
                d = _parse_dt(part, params)
                if d:
                    cur["exdates"].append(d)
    return events


# ---------------------------------------------------------------------------
# Récurrences
# ---------------------------------------------------------------------------

def expand_occurrences(start: datetime, rrule: Optional[str], exdates: List[datetime]) -> List[datetime]:
    if not rrule:
        return [start]
    ex = {d.replace(second=0, microsecond=0) for d in exdates}
    rule = re.sub(r"(UNTIL=\d{8}T\d{6})Z", r"\1", rrule, flags=re.IGNORECASE)
    horizon = start + timedelta(days=DEFAULT_HORIZON_DAYS)
    has_end = re.search(r"(UNTIL|COUNT)=", rule, re.IGNORECASE) is not None
    occ: List[datetime] = []
    if HAS_DATEUTIL:
        try:
            for dt in rrulestr(rule, dtstart=start):
                if (not has_end and dt > horizon) or len(occ) >= MAX_OCCURRENCES:
                    break
                occ.append(dt)
        except Exception:
            occ = []
    if not occ:  # repli manuel : WEEKLY / DAILY avec INTERVAL, COUNT, UNTIL
        p = dict(kv.split("=", 1) for kv in rule.split(";") if "=" in kv)
        step = int(p.get("INTERVAL", 1))
        delta = timedelta(days=step) if p.get("FREQ") == "DAILY" else timedelta(weeks=step)
        count = int(p["COUNT"]) if "COUNT" in p else MAX_OCCURRENCES
        until = _parse_dt(p["UNTIL"].rstrip("Z"), {}) if "UNTIL" in p else (None if has_end else horizon)
        cur = start
        while len(occ) < min(count, MAX_OCCURRENCES) and (until is None or cur <= until):
            occ.append(cur)
            cur += delta
    return [d for d in occ if d.replace(second=0, microsecond=0) not in ex]


# ---------------------------------------------------------------------------
# Analyse principale
# ---------------------------------------------------------------------------

def parse_ics(raw: str, group_filter: str = "") -> Dict[str, Any]:
    """
    Retourne :
      modules : [{key, code, nom}]                 (matières réelles, dédoublonnées)
      cours   : [{module_key|None, module_code, module_nom, type_cours, date_iso,
                  heure_debut, heure_fin, salle, groupe, summary, description}]
      evals   : [{titre, date_iso, module_key|None}]   (→ table tasks)
      stats   : compteurs (lus, ignorés groupe, ignorés annulés, doublons)
    """
    stats = {"lus": 0, "ignores_groupe": 0, "ignores_annules": 0, "doublons": 0}
    raw_events = _read_events(raw)

    # 1) Passe 1 : matières réelles (événements non-évaluation, non-tutorat)
    candidates: List[Dict[str, Any]] = []
    name_votes: Dict[str, Dict[str, int]] = {}
    for e in raw_events:
        summary = e.get("summary", "")
        if not summary or e.get("start") is None:
            continue
        stats["lus"] += 1
        if CANCELLED_RE.search(summary) or e.get("status") == "CANCELLED":
            stats["ignores_annules"] += 1
            continue
        if not group_matches(summary, group_filter):
            stats["ignores_groupe"] += 1
            continue
        e["is_eval"] = bool(EVAL_RE.search(summary))
        e["type"] = detect_type(summary)
        candidates.append(e)
        if not e["is_eval"] and e["type"] != "TUTORAT":
            nom = clean_summary(summary)
            key = normalize_key(nom)
            e["key"] = key
            e["nom"] = nom
            name_votes.setdefault(key, {})
            name_votes[key][nom] = name_votes[key].get(nom, 0) + 1

    modules: List[Dict[str, str]] = []
    taken: set = set()
    key_to_module: Dict[str, Dict[str, str]] = {}
    for key, votes in name_votes.items():
        nom = sorted(votes.items(), key=lambda kv: (-kv[1], -len(kv[0])))[0][0]
        mod = {"key": key, "code": make_code(nom, taken), "nom": nom}
        modules.append(mod)
        key_to_module[key] = mod

    def match_module(name: str) -> Optional[Dict[str, str]]:
        k = normalize_key(name)
        if not k:
            return None
        if k in key_to_module:
            return key_to_module[k]
        for mk, mod in key_to_module.items():  # « Technologies Web 1 » dans « TP noté Technologies Web 1 »
            if mk and (mk in k or k in mk):
                return mod
        return None

    # 2) Passe 2 : séances + évaluations
    cours: List[Dict[str, Any]] = []
    evals: List[Dict[str, Any]] = []
    seen_cours, seen_evals = set(), set()

    for e in candidates:
        summary = e.get("summary", "")
        occurrences = expand_occurrences(e["start"], e.get("rrule"), e.get("exdates", []))
        duration = (e["end"] - e["start"]) if e.get("end") else None
        salle = e.get("location") or None
        desc = (e.get("description") or "")[:500] or None
        groups = _group_tokens(summary)
        groupe = ", ".join(f"INFO{y}{''.join(sorted(l))}" for y, l in groups) or None

        if e["is_eval"]:
            titre = clean_eval_title(summary)
            mod = match_module(eval_target_name(summary))
            m_code = mod["code"] if mod else "EVAL"
            m_nom = titre  # l'emploi du temps affiche « CC1 Algèbre 1 », pas seulement la matière
            m_key = mod["key"] if mod else None
            type_cours = "EXAM"
        elif e["type"] == "TUTORAT":
            titre = None
            m_code, m_key = "TUTO", None
            m_nom = re.sub(r"\s*\bgroupes?\b.*$", "", clean_summary(summary), flags=re.IGNORECASE).strip() or "Tutorat"
            type_cours = "TUTORAT"
        else:
            titre = None
            mod = key_to_module[e["key"]]
            m_code, m_nom, m_key = mod["code"], mod["nom"], mod["key"]
            type_cours = e["type"]

        for start in occurrences:
            end = start + duration if duration is not None else None
            d_iso = start.strftime("%Y-%m-%d")
            h1 = None if e.get("all_day") else start.strftime("%H:%M")
            h2 = end.strftime("%H:%M") if (end and not e.get("all_day")) else None

            ckey = (m_code, type_cours, titre or m_nom, d_iso, h1, h2)
            if ckey in seen_cours:
                stats["doublons"] += 1
                continue
            seen_cours.add(ckey)
            cours.append({
                "module_key": m_key, "module_code": m_code, "module_nom": m_nom,
                "type_cours": type_cours, "date_iso": d_iso,
                "heure_debut": h1, "heure_fin": h2, "salle": salle, "groupe": groupe,
                "summary": (titre or summary)[:300], "description": desc,
            })
            if titre:
                ekey = (titre, d_iso)
                if ekey not in seen_evals:
                    seen_evals.add(ekey)
                    evals.append({"titre": titre, "date_iso": d_iso, "heure_debut": h1, "module_key": m_key})

    cours.sort(key=lambda c: (c["date_iso"], c["heure_debut"] or ""))
    evals.sort(key=lambda c: c["date_iso"])
    return {"modules": modules, "cours": cours, "evals": evals, "stats": stats}


# ---------------------------------------------------------------------------
# Téléchargement
# ---------------------------------------------------------------------------

def fetch_ics_from_url(url: str, timeout: int = 20) -> str:
    clean_url = url.strip()
    if not clean_url.startswith(("http://", "https://", "webcal://")):
        raise ValueError("L'URL doit commencer par http://, https:// ou webcal://")
    if clean_url.startswith("webcal://"):
        clean_url = "https://" + clean_url[9:]
    req = urllib.request.Request(clean_url, headers={"User-Agent": "Mozilla/5.0 AcademicTrack/3.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")
