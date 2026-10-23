# app.py — V3 IHM (Streamlit)
import os, sys, subprocess, io, shutil, ssl, smtplib, json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from datetime import datetime
import yaml
import streamlit as st

APP_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = APP_ROOT / "config"
OUT_DIR = APP_ROOT / "out"
ENV_PATH = APP_ROOT / ".env"
SOURCES_PATH = CONFIG_DIR / "sources.yaml"
UI_PREFS_PATH = CONFIG_DIR / "ui_prefs.json"

st.set_page_config(page_title="Actu to Me — Brief H₂/Énergie", layout="wide")

# ---------- Helpers ----------
def ensure_dirs():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

def load_env():
    data = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.strip().startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    return data

def save_env_safely(env_dict: dict):
    backup = ENV_PATH.with_suffix(".env.bak")
    if ENV_PATH.exists():
        backup.write_text(ENV_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    lines = [f"{k}={v}" for k, v in env_dict.items()]
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

def load_sources_yaml() -> str:
    if not SOURCES_PATH.exists():
        return "sections:\n  hydro:\n    title: \"💧 Hydrogène\"\n    feeds: []\n"
    return SOURCES_PATH.read_text(encoding="utf-8")

def save_sources_yaml_safely(text: str) -> str:
    # validate YAML before writing
    try:
        yaml.safe_load(text)  # raises if invalid
    except Exception as e:
        return f"Erreur YAML: {e}"
    # backup then write
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    backup = SOURCES_PATH.with_name(f"sources.{ts}.yaml.bak")
    if SOURCES_PATH.exists():
        backup.write_text(SOURCES_PATH.read_text(encoding='utf-8'), encoding='utf-8')
    SOURCES_PATH.write_text(text, encoding="utf-8")
    return "OK"

def load_prefs() -> dict:
    if UI_PREFS_PATH.exists():
        try:
            return json.loads(UI_PREFS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_prefs(prefs: dict):
    UI_PREFS_PATH.write_text(json.dumps(prefs, indent=2, ensure_ascii=False), encoding="utf-8")

def run_command(cmd:list[str], cwd:Path=None) -> tuple[int,str,str]:
    proc = subprocess.Popen(cmd, cwd=cwd or APP_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = proc.communicate()
    return proc.returncode, out, err

def send_email(smtp_conf: dict, subject: str, html_body: str, attachments: list[Path] | None = None) -> tuple[bool,str]:
    msg = MIMEMultipart()
    msg["From"] = smtp_conf.get("SMTP_FROM","")
    msg["To"] = smtp_conf.get("SMTP_TO","")
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    for path in attachments or []:
        try:
            part = MIMEBase('application', "octet-stream")
            part.set_payload(path.read_bytes())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="{path.name}"')
            msg.attach(part)
        except Exception as e:
            return False, f"Echec ajout pièce jointe {path.name}: {e}"
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_conf.get("SMTP_SERVER",""), int(smtp_conf.get("SMTP_PORT","587"))) as server:
            server.starttls(context=context)
            if smtp_conf.get("SMTP_USER"):
                server.login(smtp_conf.get("SMTP_USER",""), smtp_conf.get("SMTP_PASSWORD",""))
            server.sendmail(msg["From"], [msg["To"]], msg.as_string())
        return True, "Email envoyé"
    except Exception as e:
        return False, f"Echec envoi: {e}"

def run_main(params: dict) -> tuple[int, str, str]:
    # Build CLI args for src.main
    args = [sys.executable, "-m", "src.main"]
    if params.get("v2"):
        args.append("--v2")
    if params.get("export_articles"):
        args.append("--export-articles")
    if params.get("gpt_filter_titles"):
        args.append("--gpt-filter-titles")
    if params.get("html", True):
        args.append("--html")
    # Common
    args += ["--since", params.get("since","24h")]
    if params.get("sections"):
        args += ["--sections", *params["sections"]]
    args += ["--max-per-section", str(params.get("max_per_section", 12))]
    args += ["--links-per-section-max", str(params.get("links_per_section_max", 10))]
    if params.get("model"):
        args += ["--model", params["model"]]
    # Outputs
    out_html = params.get("out_html", str(OUT_DIR / "brief.html"))
    out_txt  = params.get("out_txt",  str(OUT_DIR / "brief.txt"))
    args += ["--out", out_html, "--text-out", out_txt]
    return run_command(args, cwd=APP_ROOT)

ensure_dirs()
prefs = load_prefs()
env_vars = load_env()

# ---------- Sidebar ----------
st.sidebar.title("Actu to Me — V3")
mode_epure = st.sidebar.toggle("Mode épuré", value=prefs.get("mode_epure", False))
st.sidebar.write("---")
st.sidebar.caption("Modèle (défaut .env)")
model_choice = st.sidebar.selectbox("Modèle", ["", "gpt-4o-mini", "gpt-4o", "gpt-5"], index=0)
email_enabled_default = bool(prefs.get("email_enabled", False))

# ---------- Tabs ----------
tabs = st.tabs(["Lancer", "Install & Check", "Configuration", "Aide"])

# ----- Tab Lancer -----
with tabs[0]:
    st.header("Lancer un brief")
    if mode_epure:
        since = st.text_input("Fenêtre (ex: 24h, 48h, 7d)", prefs.get("since", "24h"))
        detailed = st.checkbox("Générer “article → article”", value=prefs.get("detailed", False))
        email_enabled = st.checkbox("Envoyer par e-mail", value=email_enabled_default)
        out_html = str(OUT_DIR / "brief.html")
        out_txt  = str(OUT_DIR / "brief.txt")
        sections = prefs.get("sections_epure", ["hydro", "energy"])
        st.caption(f"Sections par défaut : {', '.join(sections)} (modifiable dans Configuration)")

        if st.button("Lancer"):
            params = dict(
                v2=True, export_articles=detailed, gpt_filter_titles=False, html=True,
                since=since, sections=sections, max_per_section=12, links_per_section_max=10,
                model=model_choice or env_vars.get("MODEL_NAME",""), out_html=out_html, out_txt=out_txt
            )
            code, out, err = run_main(params)
            st.subheader("Logs")
            st.code(out + ("\n" + err if err else ""), language="bash")
            if code == 0:
                st.success("Génération OK")
                st.markdown(f"[Ouvrir le brief HTML]({out_html})")
                if detailed:
                    base = Path(out_html).with_suffix("")
                    st.markdown(f"[Ouvrir le détail]({str(base) + '_articles.html'})")
                if email_enabled:
                    st.info("Envoi e-mail configuré dans l’onglet Configuration.")
            else:
                st.error("Échec de génération")
        # Persist
        prefs["mode_epure"] = True
        prefs["since"] = since
        prefs["detailed"] = detailed
        prefs["email_enabled"] = email_enabled
        prefs["sections_epure"] = sections
        save_prefs(prefs)

    else:
        cols = st.columns(3)
        with cols[0]:
            sections = st.multiselect("Sections", ["hydro","energy","world","finance","tech","ecom"], default=prefs.get("sections", ["hydro","energy","world"]))
            since = st.text_input("Fenêtre (ex: 24h, 48h, 7d)", prefs.get("since", "24h"))
            v2 = st.checkbox("Activer V2 (deux passes)", value=prefs.get("v2", True))
            gpt_filter_titles = st.checkbox("Filtre GPT sur titres (optionnel)", value=prefs.get("gpt_filter_titles", False))
        with cols[1]:
            max_per = st.slider("Max articles/section", min_value=5, max_value=30, value=prefs.get("max_per_section", 12))
            max_links = st.slider("Liens clés/section (1–10)", min_value=1, max_value=10, value=prefs.get("links_per_section_max", 10))
            export_articles = st.checkbox("Exporter le détail article→article", value=prefs.get("export_articles", False))
            want_html = st.checkbox("Générer HTML", value=True)
        with cols[2]:
            out_html = st.text_input("Fichier HTML de sortie", prefs.get("out_html", str(OUT_DIR / "brief.html")))
            out_txt  = st.text_input("Fichier TXT de sortie",  prefs.get("out_txt",  str(OUT_DIR / "brief.txt")))
            model = st.selectbox("Modèle (override optionnel)", ["", "gpt-4o-mini","gpt-4o","gpt-5"], index=0)

        if st.button("Lancer"):
            params = dict(
                v2=v2, export_articles=export_articles, gpt_filter_titles=gpt_filter_titles, html=want_html,
                since=since, sections=sections, max_per_section=max_per, links_per_section_max=max_links,
                model=model or model_choice or env_vars.get("MODEL_NAME",""), out_html=out_html, out_txt=out_txt
            )
            code, out, err = run_main(params)
            st.subheader("Logs")
            st.code(out + ("\n" + err if err else ""), language="bash")
            if code == 0:
                st.success("Génération OK")
                if want_html:
                    st.markdown(f"[Ouvrir le brief HTML]({out_html})")
                if export_articles:
                    base = Path(out_html).with_suffix("")
                    st.markdown(f"[Ouvrir le détail]({str(base) + '_articles.html'})")
            else:
                st.error("Échec de génération")

        # Persist
        prefs.update({
            "sections": sections, "since": since, "v2": v2, "gpt_filter_titles": gpt_filter_titles,
            "max_per_section": max_per, "links_per_section_max": max_links, "export_articles": export_articles,
            "out_html": out_html, "out_txt": out_txt
        })
        save_prefs(prefs)

# ----- Tab Install & Check -----
with tabs[1]:
    st.header("Install & Check")
    colA, colB = st.columns(2)

    with colA:
        st.subheader("Installer les dépendances")
        st.caption("Utilise l’interpréteur Python courant (venv conseillée).")
        if st.button("pip install -r requirements.txt"):
            code, out, err = run_command([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
            st.code(out + ("\n" + err if err else ""))
            st.success("Terminé" if code == 0 else "Terminé avec erreurs")

        st.subheader("Créer le dossier out/ s'il manque")
        if st.button("Créer out/"):
            ensure_dirs()
            st.success(f"OK: {OUT_DIR}")

    with colB:
        st.subheader("Check rapide")
        checks = {}
        # venv/exec
        checks["python"] = sys.executable
        # imports
        missing = []
        for mod in ["openai","feedparser","yaml","dotenv","readability","bs4","lxml","requests","newspaper"]:
            try:
                __import__(mod)
            except Exception:
                missing.append(mod)
        checks["missing_modules"] = missing
        # env
        env = load_env()
        checks["has_env"] = ENV_PATH.exists()
        checks["has_openai_key"] = bool(env.get("OPENAI_API_KEY"))
        checks["out_exists"] = OUT_DIR.exists()

        st.json(checks)
        if st.button("Mini test OpenAI (facultatif)"):
            try:
                from openai import OpenAI
                client = OpenAI(api_key=env.get("OPENAI_API_KEY",""))
                _ = client.chat.completions.create(
                    model=env.get("MODEL_NAME","gpt-4o-mini") or "gpt-4o-mini",
                    temperature=0,
                    max_tokens=5,
                    messages=[{"role":"system","content":"pong"},{"role":"user","content":"ping ?"}]
                )
                st.success("OpenAI OK")
            except Exception as e:
                st.error(f"OpenAI KO: {e}")

# ----- Tab Configuration -----
with tabs[2]:
    st.header("Configuration")

    with st.expander("Clé OpenAI (.env)", expanded=False):
        current = load_env()
        col1, col2 = st.columns(2)
        with col1:
            key = st.text_input("OPENAI_API_KEY", value=current.get("OPENAI_API_KEY",""), type="password")
            model_env = st.text_input("MODEL_NAME (optionnel)", value=current.get("MODEL_NAME",""))
        with col2:
            smtp_server = st.text_input("SMTP_SERVER", value=current.get("SMTP_SERVER",""))
            smtp_port = st.text_input("SMTP_PORT", value=current.get("SMTP_PORT","587"))
            smtp_user = st.text_input("SMTP_USER", value=current.get("SMTP_USER",""))
            smtp_password = st.text_input("SMTP_PASSWORD", value=current.get("SMTP_PASSWORD",""), type="password")
            smtp_from = st.text_input("SMTP_FROM", value=current.get("SMTP_FROM",""))
            smtp_to = st.text_input("SMTP_TO (dest. par défaut)", value=current.get("SMTP_TO",""))

        if st.button("Tester l’envoi e-mail"):
            ok, msg = send_email(
                dict(SMTP_SERVER=smtp_server, SMTP_PORT=smtp_port, SMTP_USER=smtp_user,
                     SMTP_PASSWORD=smtp_password, SMTP_FROM=smtp_from, SMTP_TO=smtp_to),
                subject="Test Actu to Me — OK",
                html_body="<b>Test OK</b> — V3 UI"
            )
            if ok: st.success(msg)
            else: st.error(msg)

        if st.button("Enregistrer .env (avec backup)"):
            new_env = current.copy()
            if key: new_env["OPENAI_API_KEY"] = key
            if model_env: new_env["MODEL_NAME"] = model_env
            for k,v in [("SMTP_SERVER",smtp_server),("SMTP_PORT",smtp_port),("SMTP_USER",smtp_user),
                        ("SMTP_PASSWORD",smtp_password),("SMTP_FROM",smtp_from),("SMTP_TO",smtp_to)]:
                if v is not None: new_env[k] = v
            save_env_safely(new_env)
            st.success(".env mis à jour (backup créé)")

    st.subheader("Sources (sources.yaml)")
    yaml_text = st.text_area("Éditeur YAML", load_sources_yaml(), height=260, placeholder="sections: ...")
    cols = st.columns(3)
    if cols[0].button("Valider YAML"):
        try:
            yaml.safe_load(yaml_text)
            st.success("YAML valide ✅")
        except Exception as e:
            st.error(f"YAML invalide: {e}")
    if cols[1].button("Enregistrer (backup auto)"):
        res = save_sources_yaml_safely(yaml_text)
        if res == "OK":
            st.success("sources.yaml mis à jour (backup créé)")
        else:
            st.error(res)
    if cols[2].button("Recharger depuis disque"):
        st.experimental_rerun()

# ----- Tab Aide -----
with tabs[3]:
    st.header("Aide & Conseils")
    st.markdown("""
- **V1** : une passe par section (rapide).  
- **V2** : deux passes — d’abord résumés article→article, puis synthèse par section (qualité ++).  
- **Filtre GPT titres** : utile si les flux sont très bruités (petit coût).  
- **Export PDF** : génère surtout du HTML; PDF possible si `weasyprint` installé.  
- **Email** : configure SMTP dans l’onglet Configuration, puis coche “Envoyer par e‑mail” en Mode épuré.
- **Jamais d’écrasement** : `.env` et `sources.yaml` sont sauvegardés avant écriture.
""")

st.caption("V3 UI — Streamlit • © 2025")
