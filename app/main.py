
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from datetime import datetime
from pydantic import BaseModel
from pathlib import Path
import asyncio
import json
import math
import re
import time
import urllib.request
import xml.etree.ElementTree as ET

app = FastAPI(title="Cyber Crisis Room")

BASE = Path(__file__).parent
SCENARIOS_DIR = BASE.parent / "scenarios"
SCENARIO_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
DEFAULT_CRISIS_TABLE = {
    "roles": [
        {
            "id": "soc",
            "name": "SOC / IT",
            "mission": "Qualifier les événements et contenir la menace",
        },
        {
            "id": "direction",
            "name": "Direction",
            "mission": "Arbitrer les priorités et valider les décisions",
        },
        {
            "id": "business",
            "name": "Métiers",
            "mission": "Évaluer les impacts sur les activités",
        },
        {
            "id": "communication",
            "name": "Communication",
            "mission": "Préparer les messages internes et externes",
        },
        {
            "id": "legal",
            "name": "Juridique / DPO",
            "mission": "Qualifier les obligations et les notifications",
        },
    ],
    "communications": [
        "Message interne aux équipes",
        "Point de situation pour la direction",
        "Message aux utilisateurs ou étudiants",
        "Préparation d'une notification réglementaire",
    ],
}

# ============================================================
# ETAT CENTRAL DE LA SIMULATION
# ============================================================

events = []
timeline = []
decisions = []

status = "idle"  # idle, running, paused, completed
start_time = None
current_step = 0
run_id = 0
simulation_task = None
timeline_counter = 0

STEP_DELAY = 8
NOMINAL_STEP_DELAY = STEP_DELAY
speed_multiplier = 1.0
CERT_FR_FEED_URL = "https://cert.cyber.gouv.fr/feed/"
cert_feed_cache = {
    "status": "unknown",
    "items": [],
    "updated_at": None,
    "error": None
}
CERT_FEED_CACHE_TTL = 600


def validate_scenario(data):
    """Valide et normalise un scénario importé ou chargé depuis le disque."""

    if not isinstance(data, dict):
        raise ValueError("Le scénario doit être un objet JSON.")

    required = ["id", "name", "events", "impacts", "decisions"]
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError("Champs obligatoires manquants : " + ", ".join(missing))

    scenario_id = data["id"]
    if not isinstance(scenario_id, str) or not SCENARIO_ID_PATTERN.fullmatch(scenario_id):
        raise ValueError("L'identifiant du scénario est invalide.")
    if not isinstance(data["events"], list) or not data["events"]:
        raise ValueError("Le scénario doit contenir au moins un événement.")
    if not isinstance(data["impacts"], list):
        raise ValueError("Le champ impacts doit être une liste.")
    if not isinstance(data["decisions"], dict):
        raise ValueError("Le champ decisions doit être un objet.")

    for event in data["events"]:
        if not isinstance(event, dict) or not all(
            field in event for field in ("time", "severity", "source", "event")
        ):
            raise ValueError("Chaque événement doit définir time, severity, source et event.")

    impact_ids = {
        impact.get("id") for impact in data["impacts"]
        if isinstance(impact, dict)
    }
    if None in impact_ids or len(impact_ids) != len(data["impacts"]):
        raise ValueError("Les impacts doivent avoir des identifiants uniques.")

    for action, definition in data["decisions"].items():
        if not isinstance(definition, dict) or not definition.get("label"):
            raise ValueError(f"La décision {action} doit définir un label.")
        if not definition.get("response_key"):
            raise ValueError(f"La décision {action} doit définir un response_key.")

    normalized = dict(data)
    normalized.setdefault("schema_version", 1)
    normalized.setdefault("version", "1.0")
    normalized.setdefault("description", "")
    normalized.setdefault("entity", "INDUSTRIA GROUP")
    normalized.setdefault("crisis_table", DEFAULT_CRISIS_TABLE)
    normalized.setdefault("step_delay", 8)
    normalized.setdefault("impact_updates", [])
    normalized.setdefault("event_overrides", [])
    if not isinstance(normalized["step_delay"], (int, float)) or normalized["step_delay"] <= 0:
        raise ValueError("step_delay doit être un nombre positif.")
    return normalized


def scenario_path(scenario_id):
    if not isinstance(scenario_id, str) or not SCENARIO_ID_PATTERN.fullmatch(scenario_id):
        raise ValueError("L'identifiant du scénario est invalide.")
    return SCENARIOS_DIR / f"{scenario_id}.json"


def load_scenario_file(path):
    try:
        with path.open(encoding="utf-8") as file:
            return validate_scenario(json.load(file))
    except json.JSONDecodeError as error:
        raise ValueError(f"JSON invalide dans {path.name} : {error.msg}") from error


def list_scenarios():
    return [
        {
            "id": scenario["id"],
            "name": scenario["name"],
            "version": scenario.get("version", "1.0"),
            "entity": scenario.get("entity", "INDUSTRIA GROUP"),
            "description": scenario.get("description", ""),
            "event_count": len(scenario["events"])
        }
        for path in sorted(SCENARIOS_DIR.glob("*.json"))
        for scenario in [load_scenario_file(path)]
    ]


SCENARIOS_DIR.mkdir(exist_ok=True)
DEFAULT_SCENARIO = load_scenario_file(SCENARIOS_DIR / "ransomware-industrial.json")
current_scenario = DEFAULT_SCENARIO
SCENARIO = current_scenario["events"]
STEP_DELAY = current_scenario["step_delay"]
NOMINAL_STEP_DELAY = STEP_DELAY


# ============================================================
# TIMELINE CENTRALE
# ============================================================

def add_timeline_entry(
    category,
    title,
    description="",
    severity="INFO",
    source="SYSTEM",
    scenario_time=None,
    metadata=None
):
    """
    Ajoute un élément dans la chronologie centrale.

    recorded_at : heure réelle de génération de l'événement.
    timestamp   : heure lisible pour l'interface.
    scenario_time : heure fictive du scénario, si disponible.
    """

    global timeline_counter

    timeline_counter += 1
    now = datetime.now()

    entry = {
        "id": timeline_counter,
        "run_id": run_id,
        "recorded_at": now.isoformat(),
        "timestamp": now.strftime("%H:%M:%S"),
        "category": category,
        "title": title,
        "description": description,
        "severity": severity,
        "source": source,
        "scenario_time": scenario_time,
        "metadata": metadata or {}
    }

    # La timeline est conservée dans l'ordre chronologique.
    timeline.append(entry)

    return entry


# ============================================================
# IMPACTS ET DECISIONS DU SCENARIO ACTIF
# ============================================================

INITIAL_IMPACTS = current_scenario["impacts"]
impacts = [dict(item) for item in INITIAL_IMPACTS]


# ============================================================
# DECISIONS DE LA CELLULE DE CRISE
# ============================================================

DECISION_DEFINITIONS = current_scenario["decisions"]
DECISION_CATALOG = {
    action: definition["label"]
    for action, definition in DECISION_DEFINITIONS.items()
}

response_actions = {
    definition["response_key"]: False
    for definition in DECISION_DEFINITIONS.values()
}


def set_active_scenario(scenario):
    global current_scenario, SCENARIO, NOMINAL_STEP_DELAY
    global INITIAL_IMPACTS, DECISION_DEFINITIONS, DECISION_CATALOG

    current_scenario = scenario
    SCENARIO = current_scenario["events"]
    NOMINAL_STEP_DELAY = current_scenario["step_delay"]
    set_speed_multiplier(1.0)
    INITIAL_IMPACTS = current_scenario["impacts"]
    DECISION_DEFINITIONS = current_scenario["decisions"]
    DECISION_CATALOG = {
        action: definition["label"]
        for action, definition in DECISION_DEFINITIONS.items()
    }
    response_actions.clear()
    response_actions.update({
        definition["response_key"]: False
        for definition in DECISION_DEFINITIONS.values()
    })


class DecisionRequest(BaseModel):
    action: str
    actor: str = "Cellule de crise"


class SpeedRequest(BaseModel):
    factor: float


def set_speed_multiplier(factor):
    global speed_multiplier, STEP_DELAY

    speed_multiplier = factor
    STEP_DELAY = NOMINAL_STEP_DELAY / factor


def fetch_cert_fr_feed():
    """Récupère les dernières publications publiques du flux RSS CERT-FR."""
    global cert_feed_cache

    now = time.time()
    if (
        cert_feed_cache["updated_at"]
        and now - cert_feed_cache["updated_at"] < CERT_FEED_CACHE_TTL
    ):
        return cert_feed_cache

    try:
        request = urllib.request.Request(
            CERT_FR_FEED_URL,
            headers={"User-Agent": "Cyber-Crisis-Room/1.0"}
        )
        with urllib.request.urlopen(request, timeout=8) as response:
            root = ET.fromstring(response.read())

        items = []
        for item in root.findall("./channel/item")[:5]:
            items.append({
                "title": item.findtext("title", default="Publication CERT-FR"),
                "link": item.findtext("link", default=CERT_FR_FEED_URL),
                "published": item.findtext("pubDate", default=""),
                "description": item.findtext("description", default="")
            })

        cert_feed_cache = {
            "status": "connected",
            "items": items,
            "updated_at": now,
            "error": None
        }
    except (OSError, ET.ParseError, ValueError) as error:
        cert_feed_cache = {
            "status": "unavailable",
            "items": [],
            "updated_at": now,
            "error": str(error)
        }

    return cert_feed_cache


# ============================================================
# EVOLUTION DES IMPACTS METIER
# ============================================================

def apply_impact_updates(updates, step):
    for update in updates:
        if update.get("min_step", update.get("step", 0)) > step:
            continue
        when_action = update.get("when_action")
        if when_action and not response_actions.get(
            DECISION_DEFINITIONS.get(when_action, {}).get("response_key", "")
        ):
            continue

        impact = next(
            (item for item in impacts if item["id"] == update.get("impact_id")),
            None
        )
        if impact is None:
            continue
        impact.update({
            key: update[key]
            for key in ("status", "detail")
            if key in update
        })


def update_impacts(step):
    """Fait évoluer les impacts métier selon le scénario et les décisions."""
    apply_impact_updates(
        [
            update for update in current_scenario.get("impact_updates", [])
            if update.get("step") == step
        ],
        step
    )


# ============================================================
# APPLICATION DES DECISIONS
# ============================================================

def apply_decision(action):
    """Applique les conséquences d'une décision de crise."""
    definition = DECISION_DEFINITIONS[action]
    response_actions[definition["response_key"]] = True
    apply_impact_updates(
        definition.get(
            "impact_updates",
            [
                update for update in current_scenario.get("impact_updates", [])
                if update.get("when_action") == action
            ]
        ),
        current_step
    )
    return definition["consequence"]


def scoring_summary():
    """Calcule un score pédagogique à partir de l'état courant de la simulation."""
    total_decisions = len(DECISION_DEFINITIONS)
    total_impacts = len(impacts)

    if not events and not decisions:
        return {
            "score": 0,
            "max_score": 100,
            "label": "NON DÉMARRÉ",
            "finalized": False,
            "breakdown": {
                "decisions": 0,
                "impacts": 0,
                "situation": 0
            }
        }

    decision_score = (
        50 * len({item["action"] for item in decisions}) / total_decisions
        if total_decisions else 50
    )
    favorable_statuses = {"operational", "contained", "recovering"}
    favorable_impacts = sum(
        item.get("status") in favorable_statuses for item in impacts
    )
    impact_score = 30 * favorable_impacts / total_impacts if total_impacts else 30
    severe_impacts = sum(
        item.get("status") in {"critical", "unavailable"} for item in impacts
    )
    situation_score = (
        20 * (1 - severe_impacts / total_impacts)
        if total_impacts else 20
    )
    score = round(decision_score + impact_score + situation_score)

    if score >= 80:
        label = "MAÎTRISE SATISFAISANTE"
    elif score >= 60:
        label = "RÉPONSE À RENFORCER"
    else:
        label = "SITUATION CRITIQUE"

    return {
        "score": score,
        "max_score": 100,
        "label": label,
        "finalized": status == "completed",
        "breakdown": {
            "decisions": round(decision_score),
            "impacts": round(impact_score),
            "situation": round(situation_score)
        }
    }


def decision_alerts():
    """Retourne les décisions non prises dont l'étape cible est atteinte."""
    alerts = []
    completed_actions = {
        item["action"] for item in decisions
    }

    for action, definition in DECISION_DEFINITIONS.items():
        if action in completed_actions:
            continue

        updates = [
            *definition.get("impact_updates", []),
            *[
                update for update in current_scenario.get("impact_updates", [])
                if update.get("when_action") == action
            ]
        ]
        relevant_steps = [
            update.get("min_step", update.get("step"))
            for update in updates
            if update.get("min_step", update.get("step")) is not None
        ]
        urgent_step = definition.get("urgent_step")
        if urgent_step is None and definition.get("min_step") is not None:
            urgent_step = definition["min_step"]
        if urgent_step is None and relevant_steps:
            urgent_step = min(relevant_steps)
        if urgent_step is None or current_step < urgent_step:
            continue

        alerts.append({
            "action": action,
            "label": definition["label"],
            "step": urgent_step,
            "severity": "CRITICAL" if current_step > urgent_step else "HIGH",
            "message": (
                f"Décision urgente à prendre : {definition['label']}"
            )
        })

    return alerts


# ============================================================
# MOTEUR DE SIMULATION
# ============================================================

async def simulate(my_run_id: int):
    global status, current_step

    try:
        while current_step < len(SCENARIO):

            # Attendre que la simulation soit en mode running.
            while status == "paused":
                await asyncio.sleep(0.2)

            if my_run_id != run_id or status != "running":
                return

            await asyncio.sleep(STEP_DELAY)

            # Vérifier que la simulation n'a pas été interrompue.
            if my_run_id != run_id or status != "running":
                continue

            event = dict(SCENARIO[current_step])

            for override in current_scenario.get("event_overrides", []):
                if (
                    override.get("step") == current_step + 1
                    and response_actions.get(
                        DECISION_DEFINITIONS.get(
                            override.get("when_action"), {}
                        ).get("response_key", "")
                    )
                ):
                    event.update(override.get("event", {}))

            received = datetime.now().strftime("%H:%M:%S")

            event_record = {
                **event,
                "received": received,
                "step": current_step + 1
            }

            events.insert(0, event_record)

            current_step += 1
            update_impacts(current_step)

            # Enregistrement dans la timeline centrale.
            add_timeline_entry(
                category="technical",
                title=event["event"],
                description=(
                    f"Technique : {event['technique']} | "
                    f"Type : {event['type']}"
                ),
                severity=event["severity"],
                source=event["source"],
                scenario_time=event["time"],
                metadata={
                    "step": current_step,
                    "technique": event["technique"],
                    "event_type": event["type"]
                }
            )

        if my_run_id == run_id:
            status = "completed"

            add_timeline_entry(
                category="system",
                title="Scénario terminé",
                description="Tous les événements du scénario ont été exécutés.",
                severity="INFO",
                source="CYBER OPS",
                metadata={
                    "scenario_total": len(SCENARIO)
                }
            )

    except asyncio.CancelledError:
        raise


# ============================================================
# PAGES WEB
# ============================================================

@app.get("/")
async def home():
    return FileResponse(BASE / "static" / "index.html")


@app.get("/images.jpeg")
async def branding_logo():
    return FileResponse(BASE / "images.jpeg", media_type="image/jpeg")


@app.get("/screen/{screen}")
async def screen(screen: str):
    if screen not in [
        "threats", "soc", "crisis", "dashboard", "war-room",
        "infrastructure", "about"
    ]:
        return {"error": "Unknown screen"}

    if screen == "war-room":
        return FileResponse(BASE / "static" / "war-room.html")

    if screen == "infrastructure":
        return FileResponse(BASE / "static" / "infrastructure.html")

    if screen == "about":
        return FileResponse(BASE / "static" / "about.html")

    if screen == "dashboard":
        return FileResponse(BASE / "static" / "dashboard.html")

    if screen == "crisis":
        return FileResponse(BASE / "static" / "crisis.html")

    return FileResponse(BASE / "static" / "index.html")


@app.get("/api/threat-feeds/cert-fr")
async def cert_fr_feed():
    feed = await asyncio.to_thread(fetch_cert_fr_feed)
    return {
        "source": "CERT-FR / ANSSI",
        "url": CERT_FR_FEED_URL,
        "status": feed["status"],
        "items": feed["items"],
        "updated_at": feed["updated_at"],
        "error": "Flux indisponible" if feed["error"] else None
    }


@app.get("/control")
async def control():
    return FileResponse(BASE / "static" / "control.html")


# ============================================================
# API : SCENARIOS
# ============================================================

def scenario_summary(scenario):
    return {
        "id": scenario["id"],
        "name": scenario["name"],
        "version": scenario.get("version", "1.0"),
        "entity": scenario.get("entity", "INDUSTRIA GROUP"),
        "description": scenario.get("description", ""),
        "event_count": len(scenario["events"])
    }


def clear_runtime_state():
    global status, start_time, current_step
    global simulation_task, run_id, timeline_counter

    run_id += 1
    if simulation_task and not simulation_task.done():
        simulation_task.cancel()

    simulation_task = None
    events.clear()
    timeline.clear()
    decisions.clear()
    timeline_counter = 0
    current_step = 0
    start_time = None
    status = "idle"
    impacts[:] = [dict(item) for item in INITIAL_IMPACTS]
    for key in response_actions:
        response_actions[key] = False


@app.get("/api/scenarios")
async def get_scenarios():
    return {
        "active": scenario_summary(current_scenario),
        "items": list_scenarios()
    }


@app.get("/api/scenarios/{scenario_id}")
async def export_scenario(scenario_id: str):
    try:
        scenario = load_scenario_file(scenario_path(scenario_id))
    except FileNotFoundError:
        return JSONResponse(status_code=404, content={"message": "Scénario introuvable"})
    except ValueError as error:
        return JSONResponse(status_code=400, content={"message": str(error)})

    return JSONResponse(
        content=scenario,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{scenario["id"]}.json"'
            )
        }
    )


@app.post("/api/scenarios/select/{scenario_id}")
async def select_scenario(scenario_id: str):
    if status in ["running", "paused"]:
        return JSONResponse(
            status_code=409,
            content={"message": "Arrêtez la simulation avant de changer de scénario."}
        )

    try:
        scenario = load_scenario_file(scenario_path(scenario_id))
    except FileNotFoundError:
        return JSONResponse(status_code=404, content={"message": "Scénario introuvable"})
    except ValueError as error:
        return JSONResponse(status_code=400, content={"message": str(error)})

    set_active_scenario(scenario)
    clear_runtime_state()
    return {"status": "selected", "scenario": scenario_summary(current_scenario)}


@app.post("/api/scenarios/import")
async def import_scenario(scenario: dict):
    if status in ["running", "paused"]:
        return JSONResponse(
            status_code=409,
            content={"message": "Arrêtez la simulation avant d'importer un scénario."}
        )

    try:
        validated = validate_scenario(scenario)
        path = scenario_path(validated["id"])
        path.write_text(
            json.dumps(validated, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8"
        )
    except (OSError, ValueError) as error:
        return JSONResponse(status_code=400, content={"message": str(error)})

    set_active_scenario(validated)
    clear_runtime_state()
    return {
        "status": "imported",
        "scenario": scenario_summary(current_scenario)
    }


# ============================================================
# API : ETAT GLOBAL
# ============================================================

@app.get("/api/state")
async def state():
    return {
        "status": status,
        "running": status == "running",
        "paused": status == "paused",
        "completed": status == "completed",
        "start_time": start_time.isoformat() if start_time else None,
        "current_step": current_step,
        "scenario_total": len(SCENARIO),
        "speed_multiplier": speed_multiplier,
        "step_delay": STEP_DELAY,
        "nominal_step_delay": NOMINAL_STEP_DELAY,
        "events": events,
        "timeline": timeline,
        "timeline_total": len(timeline),
        "response_actions": response_actions,
        "decision_catalog": [
            {
                "action": action,
                "label": definition["label"],
                "response_key": definition["response_key"],
                "urgent_step": definition.get("urgent_step")
            }
            for action, definition in DECISION_DEFINITIONS.items()
        ],
        "decision_alerts": decision_alerts(),
        "impacts": impacts,
        "decisions": decisions,
        "crisis_level": (
            "CRITICAL" if any(
                item["status"] in ["critical", "unavailable"]
                for item in impacts
            )
            else "HIGH" if events
            else "NORMAL"
        ),
        "total": len(events),
        "critical": sum(
            e["severity"] == "CRITICAL" for e in events
        ),
        "systems": len(set(
            e["source"] for e in events if e["source"] != "SOC"
        )),
        "last_event": events[0]["event"] if events
        else "Aucun incident detecte",
        "scenario": scenario_summary(current_scenario),
        "crisis_table": current_scenario.get("crisis_table", DEFAULT_CRISIS_TABLE),
        "scoring": scoring_summary()
    }


# ============================================================
# API : TIMELINE DEDIEE
# ============================================================

@app.get("/api/timeline")
async def get_timeline(limit: int = 200):
    """
    Retourne les événements de la timeline dans l'ordre chronologique.

    La timeline est partagée entre toutes les interfaces.
    """

    limit = max(1, min(limit, 1000))

    return {
        "total": len(timeline),
        "items": timeline[-limit:]
    }


# ============================================================
# API : CONTROLES DE SIMULATION
# ============================================================

@app.post("/api/speed")
async def set_simulation_speed(request: SpeedRequest):
    if (
        not math.isfinite(request.factor)
        or request.factor < 0.1
        or request.factor > 10
    ):
        return {
            "status": "error",
            "message": "La vitesse doit être comprise entre x0.1 et x10."
        }

    set_speed_multiplier(request.factor)
    return {
        "status": "updated",
        "speed_multiplier": speed_multiplier,
        "step_delay": STEP_DELAY
    }


@app.post("/api/start")
async def start():
    global status, start_time, current_step
    global simulation_task, run_id, timeline_counter

    # Ne pas réinitialiser une simulation active ou en pause.
    if status in ["running", "paused"]:
        return {"status": status}

    if simulation_task and not simulation_task.done():
        simulation_task.cancel()

    run_id += 1
    current_step = 0

    events.clear()
    timeline.clear()
    decisions.clear()
    timeline_counter = 0

    impacts[:] = [dict(item) for item in INITIAL_IMPACTS]

    for key in response_actions:
        response_actions[key] = False

    start_time = datetime.now()
    status = "running"

    add_timeline_entry(
        category="system",
        title="Simulation démarrée",
        description="Démarrage du scénario de cyberattaque.",
        severity="INFO",
        source="CYBER OPS",
        metadata={
            "scenario_total": len(SCENARIO),
            "step_delay": STEP_DELAY
        }
    )

    simulation_task = asyncio.create_task(simulate(run_id))

    return {"status": "started"}


@app.post("/api/pause")
async def pause():
    global status

    if status == "running":
        status = "paused"

        add_timeline_entry(
            category="system",
            title="Simulation mise en pause",
            description="Le scénario est temporairement suspendu.",
            severity="INFO",
            source="OPERATEUR"
        )

    return {"status": status}


@app.post("/api/resume")
async def resume():
    global status

    if status == "paused":
        status = "running"

        add_timeline_entry(
            category="system",
            title="Simulation reprise",
            description="Le scénario reprend son exécution.",
            severity="INFO",
            source="OPERATEUR"
        )

    return {"status": status}


@app.post("/api/reset")
async def reset():
    global status, start_time, current_step
    global simulation_task, run_id, timeline_counter

    run_id += 1

    if simulation_task and not simulation_task.done():
        simulation_task.cancel()

    impacts[:] = [dict(item) for item in INITIAL_IMPACTS]

    decisions.clear()

    for key in response_actions:
        response_actions[key] = False

    simulation_task = None

    events.clear()
    timeline.clear()
    timeline_counter = 0

    current_step = 0
    start_time = None
    status = "idle"

    return {"status": "reset"}


# ============================================================
# API : DECISIONS DE CRISE
# ============================================================

@app.post("/api/decisions")
async def add_decision(request: DecisionRequest):

    if request.action not in DECISION_CATALOG:
        return {
            "status": "error",
            "message": "Décision inconnue"
        }

    consequence = apply_decision(request.action)

    decision = {
        "action": request.action,
        "label": DECISION_CATALOG[request.action],
        "actor": request.actor,
        "step": current_step,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "consequence": consequence
    }

    decisions.insert(0, decision)

    # Toute décision est également enregistrée dans la timeline.
    add_timeline_entry(
        category="decision",
        title=DECISION_CATALOG[request.action],
        description=consequence,
        severity="INFO",
        source=request.actor,
        metadata={
            "action": request.action,
            "decision_label": DECISION_CATALOG[request.action]
        }
    )

    return {
        "status": "recorded",
        "decision": decision
    }


# ============================================================
# FICHIERS STATIQUES
# ============================================================

app.mount(
    "/static",
    StaticFiles(directory=BASE / "static"),
    name="static"
)
