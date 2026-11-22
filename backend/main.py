"""Local-only FastAPI bridge for the existing AllergyLab evaluation harness.

Run from the repository root:
    uv run uvicorn backend.main:app --host 127.0.0.1 --port 8000

The agent is executed through `uv run kit agent`, not called directly, so the
kit's answer validation, budget accounting, and trace writing remain intact.
Do not expose this server publicly: the supplied CodeAgent runs generated code.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import signal
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field, field_validator

ROOT = Path(__file__).resolve().parent.parent
TRACE_ROOT = (ROOT / "traces" / "appels").resolve()
POLLEN_CALENDAR = ROOT / "donnees_complementaires" / "rnsa-pollens-mensuels-france.csv"
MAX_EXECUTION_SECONDS = 300
MAX_STEP_CODE = 4000  # characters of agent code sent to the browser for each step
# A taxon whose monthly mean never reaches 1 grain/m³ is noise at national scale: not charted.
MIN_POLLEN_PEAK = 1.0
_agent_lock = asyncio.Lock()

app = FastAPI(
    title="AllergyLab Local API",
    description="Local bridge to the course's existing Python agent and datasets.",
    version="0.2.0",
)


app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 3:
            raise ValueError("La question est trop courte.")
        return stripped


class Usage(BaseModel):
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0


class Step(BaseModel):
    # Only the code the agent wrote. Its printed results can quote patient rows, so they stay in the trace.
    code: str


class AskResponse(BaseModel):
    status: Literal["reponse", "abstention"]
    value: str | int | float | None
    justification: str
    usage: Usage | None = None
    steps: list[Step] = []
    duration_s: float | None = None
    reused: bool = False  # answer taken from an earlier trace by equipe/memoire.py: no model call
    blocked: bool = False  # question turned away by equipe/outils/garde_fous.py: no model call


class ColumnSummary(BaseModel):
    name: str
    missing: int
    completeness_percent: float


class DatasetSummary(BaseModel):
    rows: int
    columns: int
    clinical_columns: int
    dosage_columns: int
    missing_cells: int
    completeness_percent: float
    chips: dict[str, int]
    sampling_months: list[int]  # patients per sampling month, January first
    sampling_month_missing: int
    fields: list[ColumnSummary]


class PollenTaxon(BaseModel):
    taxon: str
    family: str
    acc_allergens: str
    monthly_mean: list[float]  # grains per m³ per day, January first


class PollenCalendar(BaseModel):
    source: str
    taxa: list[PollenTaxon]


@app.get("/api/health")
async def health() -> dict[str, str]:
    # API health means only that the HTTP bridge is alive; it does not test the model key.
    return {"status": "ok", "service": "allergylab-api"}


@lru_cache(maxsize=1)
def _dataset_summary() -> DatasetSummary:
    # Only column-level statistics leave the Python process. No patient rows.
    from kit.donnees import COLONNE_PUCE, NB_CLINIQUES, charger

    df = charger()
    rows, cols = df.shape
    counts = df.isna().sum()
    missing = int(counts.sum())
    total = rows * cols
    months = df["Blood_Month_sample"].value_counts()
    fields = [
        ColumnSummary(
            name=str(column),
            missing=int(counts[column]),
            completeness_percent=round(100 * (rows - int(counts[column])) / rows, 1)
            if rows else 100.0,
        )
        for column in df.columns
    ]
    return DatasetSummary(
        rows=rows,
        columns=cols,
        clinical_columns=NB_CLINIQUES,
        dosage_columns=cols - NB_CLINIQUES,
        missing_cells=missing,
        completeness_percent=round(100 * (total - missing) / total, 1)
        if total else 100.0,
        chips={str(chip): int(n) for chip, n in df[COLONNE_PUCE].value_counts().items()},
        sampling_months=[int(months.get(month, 0)) for month in range(1, 13)],
        sampling_month_missing=int(df["Blood_Month_sample"].isna().sum()),
        fields=fields,
    )


@app.get("/api/dataset/summary", response_model=DatasetSummary)
async def dataset_summary() -> DatasetSummary:
    try:
        return await asyncio.to_thread(_dataset_summary)
    except Exception as exc:
        # Avoid exposing internal filesystem paths and data via HTTP errors.
        raise HTTPException(
            status_code=503, detail="Le tableau ne se charge pas. Lance uv run kit controle dans le terminal."
        ) from exc


@lru_cache(maxsize=1)
def _pollen_calendar() -> PollenCalendar:
    import pandas as pd

    table = pd.read_csv(POLLEN_CALENDAR, encoding="utf-8", keep_default_na=False)
    # Only the pollens and moulds that match a dosage column of the patient table.
    table = table[table["allergenes_acc"] != ""]
    taxa = []
    for taxon, group in table.groupby("taxon", sort=False):
        by_month = dict(zip(group["mois"], group["moyenne_grains_m3"]))
        if max(by_month.values()) < MIN_POLLEN_PEAK:
            continue
        taxa.append(PollenTaxon(
            taxon=str(taxon),
            family=str(group["famille"].iloc[0]),
            acc_allergens=str(group["allergenes_acc"].iloc[0]),
            monthly_mean=[float(by_month.get(month, 0.0)) for month in range(1, 13)],
        ))
    return PollenCalendar(
        source="RNSA, Ministère chargé de la santé, data.gouv.fr, Licence Ouverte 2.0 (1987-2024)",
        taxa=taxa,
    )


@app.get("/api/pollens/calendar", response_model=PollenCalendar)
async def pollen_calendar() -> PollenCalendar:
    try:
        return await asyncio.to_thread(_pollen_calendar)
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail="Le calendrier pollinique est introuvable dans donnees_complementaires/."
        ) from exc


def _from_trace(stdout: str) -> dict | None:
    """Read the validated answer from the trace written by `kit agent`."""
    match = re.search(r"(?m)^Trace\s*:\s*(.+?)\s*$", stdout)
    if not match:
        return None

    candidate = (ROOT / match.group(1).strip()).resolve()
    if not candidate.is_relative_to(TRACE_ROOT) or candidate.suffix != ".json":
        return None

    try:
        data = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _from_cli(stdout: str) -> dict | None:
    """Compatibility fallback if the trace file is not readable."""
    values: dict[str, str] = {}
    for line in stdout.splitlines():
        match = re.match(r"^\s{2,}(statut|valeur|justification)\s{2,}(.*)$", line)
        if match:
            values[match.group(1)] = match.group(2).strip()
    if {"statut", "valeur", "justification"}.issubset(values):
        return {"reponse": values}
    return None


def _parse_answer(stdout: str) -> AskResponse:
    trace = _from_trace(stdout) or _from_cli(stdout)
    if not trace:
        raise HTTPException(status_code=502, detail="La réponse de l'agent est illisible.")

    answer = trace.get("reponse")
    if not isinstance(answer, dict):
        raise HTTPException(status_code=502, detail="La trace ne contient pas de réponse.")

    status = answer.get("statut")
    if status not in ("reponse", "abstention"):
        raise HTTPException(status_code=502, detail="L'agent a rendu un statut non valide.")

    justification = answer.get("justification")
    if not isinstance(justification, str) or not justification.strip():
        raise HTTPException(status_code=502, detail="L'agent a rendu une justification vide.")

    value = answer.get("valeur")
    if status == "abstention":
        value = None
    elif not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise HTTPException(status_code=502, detail="L'agent a rendu une valeur non valide.")

    tokens = trace.get("jetons") or {}
    if not isinstance(tokens, dict):
        tokens = {}

    usage = None
    if trace.get("modele"):
        usage = Usage(
            model=str(trace["modele"]),
            input_tokens=int(tokens.get("entree") or 0),
            output_tokens=int(tokens.get("sortie") or 0),
            estimated_cost_usd=float(trace.get("cout_estime") or 0),
        )

    steps = []
    for step in trace.get("etapes") or []:
        code = step.get("code") if isinstance(step, dict) else None
        if isinstance(code, str) and code.strip():
            steps.append(Step(code=code.strip()[:MAX_STEP_CODE]))

    duration = trace.get("duree_s")
    return AskResponse(
        status=status,
        value=value,
        justification=justification.strip(),
        usage=usage,
        steps=steps,
        duration_s=float(duration) if isinstance(duration, (int, float)) else None,
        reused=any(step.code.startswith("# Réponse reprise") for step in steps),
        blocked=any(step.code.startswith("# Question refusée par le garde-fou") for step in steps),
    )


async def _terminate_process_tree(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    if os.name == "nt":
        # The uv launcher can spawn a Python child. Kill the tree, not just uv.exe.
        killer = await asyncio.create_subprocess_exec(
            "taskkill", "/T", "/F", "/PID", str(process.pid),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await killer.wait()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    await process.wait()


async def _run_kit(question: str) -> AskResponse:
    uv = shutil.which("uv")
    if not uv:
        raise HTTPException(status_code=503, detail="uv est introuvable : installe-le, puis relance le serveur.")

    flags: dict = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if os.name == "nt"
        else {"start_new_session": True}
    )
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["UV_NO_PROGRESS"] = "1"

    try:
        process = await asyncio.create_subprocess_exec(
            uv, "run", "kit", "agent", question,
            cwd=str(ROOT),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            **flags,
        )
    except OSError as exc:
        raise HTTPException(status_code=503, detail="Le kit AllergyLab ne démarre pas. Lance uv run kit controle.") from exc

    try:
        stdout_raw, _stderr_raw = await asyncio.wait_for(
            process.communicate(), timeout=MAX_EXECUTION_SECONDS
        )
    except asyncio.TimeoutError as exc:
        await _terminate_process_tree(process)
        raise HTTPException(
            status_code=504, detail="L'agent a dépassé cinq minutes : reformule la question, plus simple."
        ) from exc
    except asyncio.CancelledError:
        await _terminate_process_tree(process)
        raise

    stdout = stdout_raw.decode("utf-8", errors="replace")
    if process.returncode != 0:
        lower_output = stdout.lower()
        if "cagnotte épuisée" in lower_output:
            message = "Cagnotte épuisée : la limite de dépense de l'équipe est atteinte. Va voir Adrien."
        elif "clé" in lower_output and ("absente" in lower_output or "refusée" in lower_output):
            message = "La clé d'API est absente ou refusée. Enregistre-la avec uv run kit cle."
        elif "réponse illisible" in lower_output:
            message = "L'agent n'a pas rendu ses trois champs. Repose la question ; le détail est dans la trace."
        else:
            message = "L'agent a échoué. Lance uv run kit controle dans le terminal du projet."
        raise HTTPException(status_code=502, detail=message)

    return _parse_answer(stdout)


@app.post("/api/agent/ask", response_model=AskResponse)
async def ask_agent(payload: AskRequest) -> AskResponse:
    # No concurrent calls: the original harness has module-level state and a team budget.
    if _agent_lock.locked():
        raise HTTPException(status_code=429, detail="L'agent répond déjà à une question. Attends sa réponse.")
    async with _agent_lock:
        return await _run_kit(payload.question)
