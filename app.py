from __future__ import annotations

import hashlib
import hmac
import io
import json
import re
import secrets
import shutil
import sqlite3
import textwrap
from contextlib import contextmanager
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import plotly.express as px
import streamlit as st
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
EVIDENCE_DIR = DATA_DIR / "evidence"
DATABASE_PATH = DATA_DIR / "investigations.sqlite3"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".pdf", ".txt"}
PLATFORMS = ["Instagram", "Facebook", "TikTok", "X", "LinkedIn", "YouTube", "Other"]


st.set_page_config(
    page_title="SignalTrace | Investigations",
    page_icon="S",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');
    :root {
        --ink: #e8eef8; --muted: #91a1b9; --navy: #091321; --panel: #101e30;
        --line: #20334b; --cyan: #45d6df; --blue: #4a8dff; --violet: #9c79ff;
        --green: #63d5a5; --red: #ff7583;
    }
    html, body, [class*="css"] { font-family: 'Manrope', sans-serif; }
    .stApp { background: radial-gradient(ellipse at 86% 0%, #142946 0%, #091321 47%, #08111d 100%); color: var(--ink); }
    [data-testid="stSidebar"] { background: #0a1524; border-right: 1px solid #1c2d43; }
    [data-testid="stSidebar"] * { color: #d7e1ef; }
    [data-testid="stHeader"] { background: transparent; }
    h1, h2, h3 { letter-spacing: 0 !important; color: #f0f5fc; }
    h1 { font-size: 2rem !important; font-weight: 800 !important; }
    h2 { font-size: 1.28rem !important; font-weight: 700 !important; }
    p, label, [data-testid="stMarkdownContainer"] { color: #c4d0e0; }
    .brand { font-size: 1.08rem; font-weight: 800; color: #f0f5fc; padding: 8px 0 2px; }
    .brand-mark { display:inline-grid; place-items:center; width:30px; height:30px; margin-right:9px; border-radius:9px; color:#071321; background:linear-gradient(135deg,#45d6df,#4a8dff 55%,#9c79ff); }
    .eyebrow { color: var(--cyan); text-transform: uppercase; font: 500 .72rem 'DM Mono', monospace; letter-spacing: 0; }
    .subtle { color: var(--muted); font-size: .9rem; }
    .metric-card { min-height: 115px; padding: 17px 18px; border: 1px solid var(--line); border-radius: 12px; background: linear-gradient(145deg,rgba(18,34,54,.96),rgba(12,24,39,.94)); box-shadow: inset 0 1px 0 rgba(255,255,255,.025); }
    .metric-label { color: #9aacc3; font-size: .78rem; font-weight: 600; }
    .metric-value { margin-top: 9px; color:#f2f6fc; font-size:1.75rem; font-weight:800; line-height:1.1; }
    .metric-accent { height:2px; width:42px; margin-top:12px; border-radius:3px; background:linear-gradient(90deg,var(--cyan),var(--blue),var(--violet)); }
    .section-bar { margin: 22px 0 12px; padding-bottom: 10px; border-bottom:1px solid var(--line); }
    .status-panel { padding: 17px 18px; border:1px solid #23453f; border-radius:12px; background:linear-gradient(120deg,rgba(17,48,48,.65),rgba(15,29,44,.95)); }
    .status-dot { display:inline-block; width:8px; height:8px; margin-right:8px; border-radius:50%; background:var(--green); box-shadow:0 0 12px #63d5a588; }
    .dashboard-panel { height:100%; min-height:270px; padding:16px; border:1px solid #1d3150; border-radius:12px; background:linear-gradient(150deg,rgba(17,33,58,.97),rgba(13,25,45,.96)); }
    .dashboard-panel h3 { margin:0 0 14px; font-size:1rem; }
    .alert-item { padding:11px 0; border-bottom:1px solid #20334b; }
    .alert-item:last-child { border-bottom:0; }
    .alert-title { color:#e8eef8; font-size:.8rem; font-weight:700; }
    .alert-detail { color:#91a1b9; font-size:.72rem; overflow-wrap:anywhere; }
    .workflow-strip { margin:10px 0 14px; padding:8px 12px; border-left:2px solid #4a8dff; color:#9aacc3; font-size:.78rem; }
    .workflow-strip strong { color:#e8eef8; margin-right:14px; }
    .brand-subtitle { margin:3px 0 14px 39px; color:#91a1b9; font-size:.72rem; line-height:1.45; }
    .stButton > button, .stDownloadButton > button { border-radius:8px; border:1px solid #355273; background:linear-gradient(110deg,#1c3c63,#243454); color:#f4f8ff; font-weight:700; }
    .stButton > button:hover, .stDownloadButton > button:hover { border-color:var(--cyan); color:white; }
    .stTextInput input, .stTextArea textarea, .stSelectbox [data-baseweb="select"], .stDateInput input { background:#0b1726; color:#e7edf7; border-color:#2b405b; border-radius:8px; }
    [data-testid="stFileUploader"] { border:1px dashed #38516e; border-radius:10px; background:rgba(12,24,39,.55); }
    [data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:10px; overflow:hidden; }
    [data-testid="stForm"] { border:1px solid var(--line); border-radius:12px; background:rgba(13,26,42,.72); padding:18px; }
    div[data-testid="stMetric"] { background:transparent; }
    hr { border-color:var(--line); }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def connection_scope():
    connection = get_connection()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    with connection_scope() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT NOT NULL UNIQUE,
                complainant_name TEXT NOT NULL,
                email TEXT NOT NULL,
                platform TEXT NOT NULL,
                username TEXT NOT NULL,
                profile_url TEXT NOT NULL,
                original_url TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Open',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                username TEXT NOT NULL,
                profile_url TEXT NOT NULL,
                original_url TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL,
                risk_score INTEGER NOT NULL,
                risk_category TEXT NOT NULL,
                indicators TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evidence_id TEXT NOT NULL UNIQUE,
                case_id TEXT,
                original_filename TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE SET NULL
            );
            CREATE TABLE IF NOT EXISTS app_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )


def now_text() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def query_frame(sql: str, params: tuple = ()) -> pd.DataFrame:
    with connection_scope() as connection:
        return pd.read_sql_query(sql, connection, params=params)


def safe_filename_suffix(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("File type is not supported. Use PNG, JPG, WEBP, PDF, or TXT.")
    return suffix


def archive_file(uploaded_file, case_id: str | None = None) -> str:
    original_name = Path(uploaded_file.name).name
    suffix = safe_filename_suffix(original_name)
    raw_bytes = uploaded_file.getvalue()
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError("Files must be 20 MB or smaller.")
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        try:
            with Image.open(io.BytesIO(raw_bytes)) as image:
                image.verify()
        except Exception as error:
            raise ValueError("The uploaded image could not be decoded.") from error
    evidence_id = f"EVD-{secrets.token_hex(6).upper()}"
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    destination = EVIDENCE_DIR / f"{evidence_id}{suffix}"
    with destination.open("wb") as destination_file:
        shutil.copyfileobj(io.BytesIO(raw_bytes), destination_file)
    digest = hashlib.sha256(raw_bytes).hexdigest()
    with connection_scope() as connection:
        connection.execute(
            """INSERT INTO evidence
               (evidence_id, case_id, original_filename, file_type, file_size, sha256, stored_path, uploaded_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (evidence_id, case_id, original_name, suffix.lstrip("."), len(raw_bytes), digest,
             str(destination.relative_to(APP_DIR)), now_text()),
        )
    return evidence_id


def analyze_rules(platform: str, username: str, profile_url: str, original_url: str, description: str) -> tuple[int, str, list[str]]:
    score = 0
    indicators: list[str] = []
    parsed_url = urlparse(profile_url.strip())
    if parsed_url.scheme.lower() != "https":
        score += 15
        indicators.append("Profile URL does not use HTTPS")
    if not parsed_url.netloc:
        score += 15
        indicators.append("Profile URL is missing a recognizable domain")
    path_parts = [part.lower().lstrip("@") for part in parsed_url.path.split("/") if part]
    normalized_username = username.strip().lower().lstrip("@")
    if path_parts and normalized_username and normalized_username not in path_parts:
        score += 25
        indicators.append("Username does not appear in the supplied profile URL path")
    if re.search(r"\d{4,}$", normalized_username):
        score += 10
        indicators.append("Username ends with four or more digits")
    if original_url.strip() and profile_url.strip().rstrip("/").lower() == original_url.strip().rstrip("/").lower():
        score += 20
        indicators.append("Reported and original account URLs are identical")
    risk_terms = {
        "asking for money": 15,
        "payment": 10,
        "password": 10,
        "urgent": 8,
        "impersonat": 12,
        "copied photos": 10,
        "duplicate": 8,
        "threat": 10,
    }
    description_lower = description.lower()
    term_points = 0
    for term, points in risk_terms.items():
        if term in description_lower:
            indicators.append(f"Description mentions '{term}'")
            term_points += points
    score += min(term_points, 30)
    score = min(score, 100)
    category = "High" if score >= 60 else "Medium" if score >= 30 else "Low"
    if not indicators:
        indicators.append("No configured rule-based indicators were detected")
    return score, category, indicators


def record_analysis(platform: str, username: str, profile_url: str, original_url: str,
                    description: str, score: int, category: str, indicators: list[str]) -> int:
    with connection_scope() as connection:
        cursor = connection.execute(
            """INSERT INTO profiles
               (platform, username, profile_url, original_url, description, risk_score, risk_category, indicators, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (platform, username, profile_url, original_url, description, score, category,
             json.dumps(indicators), now_text()),
        )
        return int(cursor.lastrowid)


def metric_card(label: str, value: int, accent: str = "cyan") -> None:
    backgrounds = {
        "blue": "linear-gradient(125deg,rgba(28,85,180,.92),rgba(22,48,100,.9))",
        "violet": "linear-gradient(125deg,rgba(91,44,160,.92),rgba(49,39,103,.92))",
        "green": "linear-gradient(125deg,rgba(14,123,104,.92),rgba(17,69,75,.92))",
        "red": "linear-gradient(125deg,rgba(128,43,82,.92),rgba(65,35,75,.92))",
    }
    background = backgrounds.get(accent, "linear-gradient(145deg,rgba(18,34,54,.96),rgba(12,24,39,.94))")
    st.markdown(
        f'<div class="metric-card" style="background:{background}"><div class="metric-label">{escape(label)}</div>'
        f'<div class="metric-value">{value:,}</div><div class="metric-accent" style="background:linear-gradient(90deg,var(--{accent}),var(--blue),var(--violet))"></div></div>',
        unsafe_allow_html=True,
    )


def chart_empty(message: str) -> None:
    st.markdown(
        f'<div class="metric-card"><div class="subtle">{escape(message)}</div></div>',
        unsafe_allow_html=True,
    )


def render_dashboard() -> None:
    st.markdown('<div class="eyebrow">Detect &nbsp;·&nbsp; Analyze &nbsp;·&nbsp; Protect</div>', unsafe_allow_html=True)
    st.title("Social Media Impersonation & Evidence Personation")
    cases = query_frame("SELECT * FROM cases")
    profiles = query_frame("SELECT * FROM profiles")
    evidence = query_frame("SELECT * FROM evidence")
    open_cases = int((cases["status"] != "Resolved").sum()) if not cases.empty else 0
    resolved_cases = int((cases["status"] == "Resolved").sum()) if not cases.empty else 0
    suspicious = int((profiles["risk_category"] == "High").sum()) if not profiles.empty else 0
    low_risk = int((profiles["risk_category"] == "Low").sum()) if not profiles.empty else 0
    metric_columns = st.columns(4, gap="small")
    metrics = [
        ("Total Profiles Analyzed", len(profiles), "blue"),
        ("High-risk Profiles", suspicious, "violet"),
        ("Low-risk Profiles", low_risk, "green"),
        ("Evidence Archived", len(evidence), "red"),
    ]
    for column, (label, value, accent) in zip(metric_columns, metrics):
        with column:
            metric_card(label, value, accent)
    st.markdown(
        f'<div class="workflow-strip">Case workflow: '
        f'<strong>{open_cases} open</strong><strong>{resolved_cases} resolved</strong>'
        'Counts reflect saved investigations.</div>',
        unsafe_allow_html=True,
    )

    trend_col, evidence_col, alerts_col = st.columns([1.4, 1.05, .8], gap="small")
    with trend_col:
        st.markdown('<div class="dashboard-panel"><h3>Impersonation Trends</h3>', unsafe_allow_html=True)
        if cases.empty and profiles.empty:
            chart_empty("Report and analysis trends will appear as records are added.")
        else:
            months = pd.period_range(end=pd.Timestamp.now().to_period("M"), periods=6, freq="M")
            case_counts = pd.Series(dtype="int64", index=months)
            profile_counts = pd.Series(dtype="int64", index=months)
            if not cases.empty:
                case_months = pd.to_datetime(cases["created_at"]).dt.to_period("M")
                case_counts = case_months.value_counts().reindex(months, fill_value=0).sort_index()
            if not profiles.empty:
                profile_months = pd.to_datetime(profiles["created_at"]).dt.to_period("M")
                profile_counts = profile_months.value_counts().reindex(months, fill_value=0).sort_index()
            trend = pd.DataFrame({
                "Month": [month.strftime("%b") for month in months],
                "Reports": case_counts.to_numpy(),
                "Profiles analyzed": profile_counts.to_numpy(),
            }).melt(id_vars="Month", var_name="Activity", value_name="Count")
            fig = px.line(trend, x="Month", y="Count", color="Activity", markers=True,
                          color_discrete_map={"Reports": "#288dff", "Profiles analyzed": "#22c997"})
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#c4d0e0",
                             margin=dict(l=4,r=4,t=18,b=2), height=220, legend_title=None,
                             legend=dict(orientation="h", y=1.12, x=0.1), xaxis_title=None, yaxis_title=None)
            fig.update_xaxes(showgrid=False)
            fig.update_yaxes(gridcolor="#20334b", rangemode="tozero", dtick=1)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)
    with evidence_col:
        st.markdown('<div class="dashboard-panel"><h3>Evidence Types</h3>', unsafe_allow_html=True)
        if evidence.empty:
            chart_empty("Archived file distribution will appear here.")
        else:
            types = evidence.groupby("file_type", as_index=False).size().rename(columns={"file_type": "Type", "size": "Files"})
            fig = px.pie(types, values="Files", names="Type", hole=.62,
                         color_discrete_sequence=["#288dff", "#9c4bd2", "#22c997", "#ff8b38", "#e34d68"])
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#c4d0e0",
                              margin=dict(l=2,r=2,t=8,b=0), height=220, legend_title=None,
                              legend=dict(font=dict(size=10)))
            fig.update_traces(textinfo="percent", textposition="inside", textfont_color="white")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)
    with alerts_col:
        st.markdown('<div class="dashboard-panel"><h3>Recent Alerts</h3>', unsafe_allow_html=True)
        alert_rows = []
        for _, record in cases.iterrows():
            alert_rows.append((record["created_at"], "Report submitted", f'{record["case_id"]} · @{record["username"]}'))
        for _, record in profiles[profiles["risk_category"] == "High"].iterrows() if not profiles.empty else []:
            alert_rows.append((record["created_at"], "High-risk profile analysis", f'@{record["username"]} · {record["risk_score"]}/100'))
        for _, record in evidence.iterrows():
            alert_rows.append((record["uploaded_at"], "Evidence archived", f'{record["evidence_id"]} · {record["original_filename"]}'))
        alert_rows.sort(key=lambda item: item[0], reverse=True)
        if not alert_rows:
            chart_empty("New reports and archived evidence will appear here.")
        else:
            for timestamp, title, detail in alert_rows[:4]:
                display_time = datetime.fromisoformat(timestamp).strftime("%b %d · %H:%M")
                st.markdown(
                    f'<div class="alert-item"><div class="alert-title">{escape(title)}</div>'
                    f'<div class="alert-detail">{escape(detail)}<br>{escape(display_time)}</div></div>',
                    unsafe_allow_html=True,
                )
        st.markdown("</div>", unsafe_allow_html=True)

    platform_col, risk_col, status_col = st.columns([1.2, 1.1, .8], gap="small")
    with platform_col:
        st.markdown('<div class="dashboard-panel"><h3>Platform Distribution</h3>', unsafe_allow_html=True)
        if cases.empty:
            chart_empty("Platform counts will appear as reports are submitted.")
        else:
            platforms = cases.groupby("platform", as_index=False).size().rename(columns={"size": "Reports"})
            fig = px.bar(platforms, x="platform", y="Reports", color="platform",
                         color_discrete_sequence=["#288dff", "#9c4bd2", "#1ca9e8", "#e34d45", "#22c997", "#ff8b38"])
            fig.update_layout(showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              font_color="#c4d0e0", margin=dict(l=2,r=2,t=8,b=2), height=190)
            fig.update_xaxes(title=None, showgrid=False, tickfont=dict(size=10))
            fig.update_yaxes(title=None, gridcolor="#20334b", rangemode="tozero", dtick=1)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)
    with risk_col:
        st.markdown('<div class="dashboard-panel"><h3>Top Risk Profiles</h3>', unsafe_allow_html=True)
        if profiles.empty:
            chart_empty("Analyzed profiles will appear here, ranked by rule-based score.")
        else:
            top_profiles = profiles.sort_values(["risk_score", "created_at"], ascending=[False, False]).head(5)
            risk_table = top_profiles[["username", "risk_score", "risk_category"]].rename(
                columns={"username": "Username", "risk_score": "Risk Score", "risk_category": "Level"}
            )
            st.dataframe(risk_table, hide_index=True, use_container_width=True, height=190)
        st.markdown("</div>", unsafe_allow_html=True)
    with status_col:
        st.markdown(
            '<div class="status-panel" style="height:100%;min-height:270px;text-align:center;display:flex;flex-direction:column;justify-content:center">'
            '<div style="font-size:2.5rem;color:#22c997">✓</div><strong style="color:#22c997;font-size:1.2rem">System Status</strong>'
            '<div style="color:#45d6df;font-size:1.5rem;font-weight:800;margin:8px 0">Local only</div>'
            '<span class="subtle">SQLite and evidence storage available</span>'
            '<span class="subtle" style="margin-top:8px">Authentication is not enabled</span></div>',
            unsafe_allow_html=True,
        )


def render_analyze_profile() -> None:
    st.markdown('<div class="eyebrow">Triage</div>', unsafe_allow_html=True)
    st.title("Analyze a profile")
    st.caption("Rule-based indicators support triage; they do not establish impersonation or intent.")
    with st.form("profile_analysis"):
        platform = st.selectbox("Social media platform", PLATFORMS)
        username = st.text_input("Profile username", placeholder="@username")
        profile_url = st.text_input("Profile URL", placeholder="https://…")
        original_url = st.text_input("Original account URL (optional)", placeholder="https://…")
        description = st.text_area("Describe the suspicious activity", height=120)
        screenshot = st.file_uploader("Profile screenshot (optional)", type=["png", "jpg", "jpeg", "webp"], key="analysis_screenshot")
        submitted = st.form_submit_button("Analyze profile", type="primary")
    if submitted:
        if not username.strip() or not profile_url.strip() or not description.strip():
            st.error("Enter a username, profile URL, and activity description to analyze.")
        else:
            score, category, indicators = analyze_rules(platform, username, profile_url, original_url, description)
            record_analysis(platform, username.strip(), profile_url.strip(), original_url.strip(), description.strip(), score, category, indicators)
            evidence_id = None
            if screenshot is not None:
                try:
                    evidence_id = archive_file(screenshot)
                except ValueError as error:
                    st.warning(f"Analysis saved, but screenshot was not archived: {error}")
            st.session_state["last_analysis"] = {
                "platform": platform, "username": username.strip(), "profile_url": profile_url.strip(),
                "score": score, "category": category, "indicators": indicators, "evidence_id": evidence_id,
            }
    result = st.session_state.get("last_analysis")
    if result:
        st.markdown('<div class="section-bar"><h2>Analysis result</h2></div>', unsafe_allow_html=True)
        score_col, detail_col = st.columns([1, 2])
        with score_col:
            st.metric("Rule-based risk score", f"{result['score']} / 100", result["category"])
        with detail_col:
            st.markdown(f"**{escape(result['platform'])}** · {escape(result['username'])}")
            st.markdown(f"Profile: {escape(result['profile_url'])}")
            st.markdown("**Observed indicators**")
            for indicator in result["indicators"]:
                st.markdown(f"- {escape(indicator)}")
        if result.get("evidence_id"):
            st.info(f"Screenshot archived as {result['evidence_id']}.")
        st.info("Recommended next steps: independently review the profile and source material, preserve relevant context, contact the affected person through a known channel, and submit a report if appropriate. A score is not a definitive AI determination or proof of impersonation.")


def render_report_impersonation() -> None:
    st.markdown('<div class="eyebrow">Intake</div>', unsafe_allow_html=True)
    st.title("Report impersonation")
    st.caption("Submitted reports are stored locally as investigation cases.")
    with st.form("report_case"):
        complainant = st.text_input("Complainant name")
        email = st.text_input("Email address")
        platform = st.selectbox("Social media platform", PLATFORMS, key="report_platform")
        username = st.text_input("Fake profile username")
        profile_url = st.text_input("Fake profile URL")
        original_url = st.text_input("Original account URL")
        description = st.text_area("Describe the impersonation and its impact", height=130)
        attachment = st.file_uploader("Screenshot or supporting evidence (optional)", type=["png", "jpg", "jpeg", "webp", "pdf", "txt"], key="report_evidence")
        submitted = st.form_submit_button("Submit report", type="primary")
    if submitted:
        if not all(value.strip() for value in (complainant, email, username, profile_url, original_url, description)):
            st.error("Complete all required fields before submitting.")
        elif not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email.strip()):
            st.error("Enter a valid email address.")
        elif not (profile_url.strip().startswith("https://") and original_url.strip().startswith("https://")):
            st.error("Use HTTPS URLs for both profile links.")
        else:
            case_id = f"CASE-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
            with connection_scope() as connection:
                connection.execute(
                    """INSERT INTO cases
                       (case_id, complainant_name, email, platform, username, profile_url, original_url, description, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (case_id, complainant.strip(), email.strip(), platform, username.strip(), profile_url.strip(),
                     original_url.strip(), description.strip(), now_text()),
                )
            if attachment is not None:
                try:
                    evidence_id = archive_file(attachment, case_id)
                    st.success(f"Case {case_id} created. Evidence archived as {evidence_id}.")
                except ValueError as error:
                    st.warning(f"Case {case_id} created, but attachment was not archived: {error}")
            else:
                st.success(f"Case {case_id} created.")


def render_evidence_archive() -> None:
    st.markdown('<div class="eyebrow">Chain of custody</div>', unsafe_allow_html=True)
    st.title("Evidence archive")
    st.caption("Files are stored locally. Each item is recorded with its SHA-256 digest and upload metadata.")
    cases = query_frame("SELECT case_id FROM cases ORDER BY created_at DESC")
    case_options = ["Unlinked"] + cases["case_id"].tolist()
    with st.form("archive_evidence"):
        uploaded = st.file_uploader("Choose evidence files", type=["png", "jpg", "jpeg", "webp", "pdf", "txt"], accept_multiple_files=True)
        linked_case = st.selectbox("Link to case", case_options)
        submitted = st.form_submit_button("Archive selected files", type="primary")
    if submitted:
        if not uploaded:
            st.warning("Choose at least one file.")
        else:
            archived = []
            errors = []
            for file in uploaded:
                try:
                    archived.append((Path(file.name).name, archive_file(file, None if linked_case == "Unlinked" else linked_case)))
                except ValueError as error:
                    errors.append(f"{file.name}: {error}")
            for filename, evidence_id in archived:
                st.success(f"Archived {filename} as {evidence_id}.")
            for error in errors:
                st.error(error)
    records = query_frame(
        """SELECT e.evidence_id AS 'Evidence ID', e.original_filename AS Filename, e.file_type AS Type,
                  e.file_size AS 'Size (bytes)', e.sha256 AS 'SHA-256', e.case_id AS 'Case ID', e.uploaded_at AS 'Uploaded'
           FROM evidence e ORDER BY e.id DESC"""
    )
    st.markdown('<div class="section-bar"><h2>Archived files</h2></div>', unsafe_allow_html=True)
    search = st.text_input("Search by filename, evidence ID, or case ID", key="evidence_search")
    type_filter = st.selectbox("Filter by file type", ["All"] + sorted(records["Type"].dropna().unique().tolist()) if not records.empty else ["All"])
    filtered = records.copy()
    if search:
        mask = filtered.astype(str).apply(lambda column: column.str.contains(search, case=False, na=False)).any(axis=1)
        filtered = filtered[mask]
    if type_filter != "All":
        filtered = filtered[filtered["Type"] == type_filter]
    if filtered.empty:
        chart_empty("No matching archived files.")
    else:
        st.dataframe(filtered.drop(columns=["SHA-256"]), hide_index=True, use_container_width=True)
        selected = st.selectbox("Inspect evidence digest", filtered["Evidence ID"].tolist())
        selected_record = filtered[filtered["Evidence ID"] == selected].iloc[0]
        st.code(selected_record["SHA-256"], language=None)


def render_verify_evidence() -> None:
    st.markdown('<div class="eyebrow">Integrity check</div>', unsafe_allow_html=True)
    st.title("Verify evidence")
    st.caption("A matching digest means the archived file matches its recorded version. It does not prove authenticity or origin.")
    evidence = query_frame("SELECT evidence_id, original_filename, sha256, stored_path, uploaded_at FROM evidence ORDER BY id DESC")
    if evidence.empty:
        chart_empty("There are no archived files to verify yet.")
        return
    labels = {row["evidence_id"]: f"{row['evidence_id']} · {row['original_filename']}" for _, row in evidence.iterrows()}
    selected_id = st.selectbox("Select archived evidence", evidence["evidence_id"].tolist(), format_func=lambda value: labels[value])
    if st.button("Recalculate SHA-256", type="primary"):
        selected = evidence[evidence["evidence_id"] == selected_id].iloc[0]
        file_path = (APP_DIR / selected["stored_path"]).resolve()
        if not file_path.is_relative_to(EVIDENCE_DIR.resolve()):
            st.error("Stored path is outside the configured evidence directory. Verification stopped.")
            return
        verification_time = now_text()
        if not file_path.is_file():
            st.error(f"Archived file is missing. Evidence ID: {selected_id}. Checked: {verification_time}")
            return
        digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
        matches = hmac.compare_digest(digest, selected["sha256"])
        st.markdown(f"**Evidence ID:** `{selected_id}`  \n**Verification timestamp:** {verification_time}")
        if matches:
            st.success("UNCHANGED: the file matches the SHA-256 digest recorded at archive time.")
        else:
            st.error("MISMATCH: the file differs from the version recorded at archive time.")
        st.caption("Hash comparison verifies file consistency only; it is not proof that the content is genuine.")


def build_case_pdf(case: pd.Series, evidence: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    document = SimpleDocTemplate(output, pagesize=letter, rightMargin=.65 * inch, leftMargin=.65 * inch,
                                 topMargin=.65 * inch, bottomMargin=.65 * inch)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], textColor=colors.HexColor("#10233a"), alignment=TA_LEFT, fontName="Helvetica-Bold", fontSize=20))
    styles.add(ParagraphStyle(name="ReportBody", parent=styles["BodyText"], leading=15, spaceAfter=8))
    story = [Paragraph("Investigation Case Report", styles["ReportTitle"]), Spacer(1, 8)]
    story.append(Paragraph(f"<b>Case ID:</b> {escape(str(case['case_id']))} &nbsp;&nbsp; <b>Status:</b> {escape(str(case['status']))}", styles["ReportBody"]))
    story.append(Paragraph(f"<b>Generated:</b> {escape(now_text())}", styles["ReportBody"]))
    story.append(Paragraph("Case details", styles["Heading2"]))
    details = [
        ["Complainant", str(case["complainant_name"])], ["Email", str(case["email"])],
        ["Platform", str(case["platform"])], ["Reported username", str(case["username"])],
        ["Profile URL", str(case["profile_url"])], ["Original URL", str(case["original_url"])],
        ["Reported", str(case["created_at"])],
    ]
    table = Table([[Paragraph(escape(a), styles["BodyText"]), Paragraph(escape(b), styles["BodyText"])] for a, b in details], colWidths=[1.35 * inch, 5.2 * inch])
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (0,-1), colors.HexColor("#eaf0f6")), ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#cbd5e1")), ("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 7), ("RIGHTPADDING", (0,0), (-1,-1), 7), ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6)]))
    story.extend([table, Spacer(1, 12), Paragraph("Description", styles["Heading2"]), Paragraph(escape(str(case["description"])).replace("\n", "<br/>"), styles["ReportBody"]), Paragraph("Linked evidence", styles["Heading2"])])
    if evidence.empty:
        story.append(Paragraph("No evidence is linked to this case.", styles["ReportBody"]))
    else:
        rows = [["Evidence ID", "Filename", "Type", "Bytes", "SHA-256"]]
        for _, record in evidence.iterrows():
            rows.append([str(record["evidence_id"]), str(record["original_filename"]), str(record["file_type"]), str(record["file_size"]), str(record["sha256"])])
        wrapped = [[Paragraph(escape(value), styles["BodyText"]) for value in row] for row in rows]
        evidence_table = Table(wrapped, repeatRows=1, colWidths=[.85*inch, 1.5*inch, .55*inch, .55*inch, 3.1*inch])
        evidence_table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#dbe7f3")), ("GRID", (0,0), (-1,-1), .3, colors.HexColor("#cbd5e1")), ("VALIGN", (0,0), (-1,-1), "TOP"), ("FONTSIZE", (0,0), (-1,-1), 7), ("LEFTPADDING", (0,0), (-1,-1), 4), ("RIGHTPADDING", (0,0), (-1,-1), 4)]))
        story.append(evidence_table)
    story.extend([Spacer(1, 18), Paragraph("This report is generated from records stored in the local application. A matching evidence digest confirms file consistency with the archived copy only; it does not establish authenticity.", styles["Italic"] )])
    document.build(story)
    return output.getvalue()


def render_reports() -> None:
    st.markdown('<div class="eyebrow">Documentation</div>', unsafe_allow_html=True)
    st.title("Investigation reports")
    st.caption("Generate a case-specific PDF containing the complaint and linked evidence metadata.")
    cases = query_frame("SELECT * FROM cases ORDER BY created_at DESC")
    if cases.empty:
        chart_empty("No cases are available. Submit an impersonation report to generate a case report.")
        return
    case_options = cases["case_id"].tolist()
    selected_id = st.selectbox("Select investigation", case_options)
    case = cases[cases["case_id"] == selected_id].iloc[0]
    status_options = ["Open", "Under Review", "Resolved"]
    current_status = case["status"] if case["status"] in status_options else "Open"
    with st.form("update_case_status"):
        updated_status = st.selectbox("Case status", status_options, index=status_options.index(current_status))
        status_submitted = st.form_submit_button("Update case status")
    if status_submitted and updated_status != current_status:
        with connection_scope() as connection:
            connection.execute("UPDATE cases SET status = ? WHERE case_id = ?", (updated_status, selected_id))
        st.success("Case status updated.")
        st.rerun()
    linked_evidence = query_frame("SELECT evidence_id, original_filename, file_type, file_size, sha256 FROM evidence WHERE case_id = ? ORDER BY uploaded_at", (selected_id,))
    st.markdown(f"**{escape(case['case_id'])}** · {escape(case['platform'])} · {escape(case['username'])} · {escape(case['status'])}")
    st.write(textwrap.shorten(str(case["description"]), width=360, placeholder="…"))
    st.write(f"Linked evidence files: {len(linked_evidence)}")
    pdf_bytes = build_case_pdf(case, linked_evidence)
    st.download_button("Download case report PDF", pdf_bytes, file_name=f"{selected_id.lower()}-report.pdf", mime="application/pdf", type="primary")
    if not linked_evidence.empty:
        st.dataframe(linked_evidence.rename(columns={"evidence_id": "Evidence ID", "original_filename": "Filename", "file_type": "Type", "file_size": "Size (bytes)", "sha256": "SHA-256"}), hide_index=True, use_container_width=True)


def render_user_management() -> None:
    st.markdown('<div class="eyebrow">Workspace administration</div>', unsafe_allow_html=True)
    st.title("User management")
    st.warning("This local prototype stores a team directory only. It does not authenticate users or enforce role-based access.")
    with st.form("add_user"):
        name = st.text_input("Name")
        email = st.text_input("Email", key="user_email")
        role = st.selectbox("Role", ["Investigator", "Reviewer", "Administrator"])
        submitted = st.form_submit_button("Add directory entry")
    if submitted:
        if not name.strip() or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email.strip()):
            st.error("Enter a name and a valid email address.")
        else:
            try:
                with connection_scope() as connection:
                    connection.execute("INSERT INTO app_users (name, email, role, created_at) VALUES (?, ?, ?, ?)", (name.strip(), email.strip(), role, now_text()))
                st.success("Directory entry added.")
            except sqlite3.IntegrityError:
                st.error("That email address is already in the directory.")
    users = query_frame("SELECT name AS Name, email AS Email, role AS Role, created_at AS 'Added' FROM app_users ORDER BY id DESC")
    if users.empty:
        chart_empty("No directory entries yet.")
    else:
        st.dataframe(users, hide_index=True, use_container_width=True)


def render_settings() -> None:
    st.markdown('<div class="eyebrow">Configuration</div>', unsafe_allow_html=True)
    st.title("Settings")
    st.markdown("#### Local storage")
    st.write(f"Database: `{DATABASE_PATH}`")
    st.write(f"Evidence directory: `{EVIDENCE_DIR}`")
    st.write(f"Maximum file size: {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    st.markdown("#### Supported evidence")
    st.write(", ".join(sorted(extension.lstrip(".").upper() for extension in ALLOWED_EXTENSIONS)))
    st.warning("This prototype stores evidence unencrypted on the host filesystem. Restrict host access, back up the data directory securely, and add authentication and encryption before handling sensitive real-world cases or exposing it to a network.")


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    initialize_database()
    st.sidebar.markdown(
        '<div class="brand"><span class="brand-mark">S</span>SIEP</div>'
        '<div class="brand-subtitle">Social Media Impersonation &amp; Evidence Archiving</div>',
        unsafe_allow_html=True,
    )
    st.sidebar.markdown("---")
    pages = ["Dashboard", "Analyze Profile", "Report Impersonation", "Evidence Archive", "Verify Evidence", "Investigation Reports", "User Management", "Settings", "Logout"]
    page = st.sidebar.radio("Navigation", pages, label_visibility="collapsed")
    st.sidebar.markdown("---")
    st.sidebar.markdown('<span class="status-dot"></span><span class="subtle">Local workspace</span>', unsafe_allow_html=True)
    if page == "Dashboard":
        render_dashboard()
    elif page == "Analyze Profile":
        render_analyze_profile()
    elif page == "Report Impersonation":
        render_report_impersonation()
    elif page == "Evidence Archive":
        render_evidence_archive()
    elif page == "Verify Evidence":
        render_verify_evidence()
    elif page == "Investigation Reports":
        render_reports()
    elif page == "User Management":
        render_user_management()
    elif page == "Settings":
        render_settings()
    else:
        st.title("End local session")
        st.info("This prototype has no authenticated session to revoke. Clear transient page state and close the browser tab when finished.")
        if st.button("Clear transient session state"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


if __name__ == "__main__":
    main()