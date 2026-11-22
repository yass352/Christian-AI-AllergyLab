
import os
import re
import shutil
import subprocess
from pathlib import Path

import streamlit as st
from kit.donnees import charger

ROOT = Path(__file__).resolve().parent.parent

st.set_page_config(
    page_title="Christian AI",
    page_icon="🧬",
    layout="wide",
)


def run_agent(question: str) -> tuple[str, str | None]:
    """Run the official kit command and capture its response."""

    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv is not installed or not in PATH.")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    result = subprocess.run(
        [uv, "run", "kit", "agent", question],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
        env=env,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "The agent failed. Run 'uv run kit controle' "
            "and test the question directly in your terminal."
        )

    fields = {}
    usage = None

    for line in result.stdout.splitlines():
        match = re.match(
            r"^\s{2,}(statut|valeur|justification)\s{2,}(.*)$",
            line,
        )

        if match:
            fields[match.group(1)] = match.group(2).strip()

        if line.startswith("Jetons :"):
            usage = line

    required = {"statut", "valeur", "justification"}

    if not required.issubset(fields):
        raise RuntimeError("The agent response could not be parsed.")

    if fields["statut"] == "abstention":
        answer = (
            "**Abstention**\n\n"
            + fields["justification"]
        )
    else:
        answer = (
            f"**Réponse :** {fields['valeur']}\n\n"
            f"**Justification :** {fields['justification']}"
        )

    return answer, usage


@st.cache_data(show_spinner=False)
def load_dataset():
    """Load data using the official kit loader."""
    return charger()


st.title("🧬 Christian AI")
st.caption("Assistant intelligent d'analyse des allergies")

chat_tab, data_tab = st.tabs([
    "💬 Assistant IA",
    "📊 Données",
])

with chat_tab:
    st.subheader("Assistant d'analyse")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if st.button("Nouvelle conversation"):
        st.session_state.messages = []
        st.rerun()

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            if message.get("usage"):
                st.caption(message["usage"])

    prompt = st.chat_input(
        "Posez une question sur les allergies..."
    )

    if prompt:
        prompt = prompt.strip()

        if len(prompt) > 2000:
            st.warning("Maximum 2000 caractères.")
            st.stop()

        st.session_state.messages.append({
            "role": "user",
            "content": prompt,
        })

        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            try:
                with st.spinner("Analyse en cours..."):
                    answer, usage = run_agent(prompt)

            except subprocess.TimeoutExpired:
                st.error(
                    "The request timed out. Check the agent "
                    "and API status in your terminal."
                )

            except (RuntimeError, OSError) as error:
                st.error(str(error))

            else:
                st.markdown(answer)

                if usage:
                    st.caption(usage)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "usage": usage,
                })


with data_tab:
    st.subheader("Exploration du dataset")

    if st.button("Charger les données"):
        try:
            df = load_dataset()

        except Exception:
            st.error("Impossible de charger les données.")

        else:
            col1, col2 = st.columns(2)

            col1.metric("Patients", f"{len(df):,}")
            col2.metric("Colonnes", len(df.columns))

            st.dataframe(
                df.head(20),
                width="stretch",
            )

            st.write("Valeurs manquantes par colonne")
            st.dataframe(
                df.isna().sum().rename("Manquantes"),
                width="stretch",
            )
