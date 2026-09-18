import streamlit as st
import pandas as pd
import requests
import zipfile
import json
from pathlib import Path
from io import BytesIO

st.set_page_config(page_title="CPL Predictor", page_icon="🏏", layout="wide")
st.title("🏏 CPL Predictor + Cricsheet")

# ==========================================
# SESSION STATE
# ==========================================
if "history" not in st.session_state:
    st.session_state.history = []
if "cricsheet_df" not in st.session_state:
    st.session_state.cricsheet_df = pd.DataFrame()

# ==========================================
# CRICSHEET SYNC
# ==========================================
CRICSHEET_URL = "https://cricsheet.org/downloads/cpl_male_json.zip"

def sync_cricsheet():
    """Download Cricsheet CPL zip and parse all matches."""
    r = requests.get(CRICSHEET_URL, timeout=60)
    r.raise_for_status()

    rows = []
    with zipfile.ZipFile(BytesIO(r.content)) as z:
        for name in z.namelist():
            if not name.endswith(".json"):
                continue
            try:
                data = json.loads(z.read(name))
            except Exception:
                continue

            info = data.get("info", {})
            teams = info.get("teams", [])
            toss = info.get("toss", {})
            outcome = info.get("outcome", {})

            rows.append({
                "match_id": Path(name).stem,
                "date": (info.get("dates") or [None])[0],
                "venue": info.get("venue", ""),
                "team1": teams[0] if len(teams) > 0 else None,
                "team2": teams[1] if len(teams) > 1 else None,
                "toss_winner": toss.get("winner"),
                "toss_decision": toss.get("decision"),
                "winner": outcome.get("winner"),
            })

    return pd.DataFrame(rows).sort_values("date", ascending=False)


# ==========================================
# TABS
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs(["🔮 Predict", "📡 Live", "📊 History", "🔄 Cricsheet"])


# ------------------------------------------
# TAB 1: PREDICT
# ------------------------------------------
with tab1:
    st.subheader("Match Setup")

    col1, col2 = st.columns(2)
    with col1:
        team1 = st.text_input("Team 1", "Guyana Amazon Warriors")
        pitch_type = st.selectbox("Pitch type", ["Spin", "Pace", "Flat", "Neutral"])
        spin1 = st.slider(f"{team1[:15]} spinners", 0, 6, 3)
        form1 = st.slider(f"{team1[:15]} wins (last 5)", 0, 5, 2)

    with col2:
        team2 = st.text_input("Team 2", "Antigua and Barbuda Falcons")
        dew = st.checkbox("Dew expected?")
        spin2 = st.slider(f"{team2[:15]} spinners", 0, 6, 4)
        form2 = st.slider(f"{team2[:15]} wins (last 5)", 0, 5, 4)

    toss_winner = st.selectbox("Toss winner", [team1, team2])
    toss_decision = st.selectbox("Decision", ["Bowl", "Bat"])

    if st.button("🔮 Predict Winner", type="primary", use_container_width=True):
        s1 = spin1 * 0.3 + form1 * 0.2
        s2 = spin2 * 0.3 + form2 * 0.2

        if toss_winner == team1:
            s1 += 0.5
        else:
            s2 += 0.5

        if pitch_type == "Spin":
            if spin1 > spin2:
                s1 += 0.5
            elif spin2 > spin1:
                s2 += 0.5

        if dew:
            s1 -= 0.2
            s2 -= 0.2

        total = s1 + s2
        p1, p2 = s1 / total * 100, s2 / total * 100
        winner = team1 if p1 > p2 else team2
        diff = abs(p1 - p2)

        conf = ("HIGH" if diff >= 25 else
                "MEDIUM-HIGH" if diff >= 15 else
                "MEDIUM" if diff >= 8 else "LOW")

        st.success(f"🏆 **{winner}** to win")
        c1, c2 = st.columns(2)
        c1.metric(team1, f"{p1:.1f}%")
        c2.metric(team2, f"{p2:.1f}%")
        st.info(f"Confidence: **{conf}** (gap: {diff:.1f}%)")

        st.session_state.history.append({
            "team1": team1, "team2": team2,
            "predicted": winner, "confidence": conf,
            "prob1": round(p1, 1), "prob2": round(p2, 1),
            "actual": None,
        })
        st.caption("✅ Saved to History tab")


# ------------------------------------------
# TAB 2: LIVE IN-PLAY
# ------------------------------------------
with tab2:
    st.subheader("📡 Live Win Probability")

    target = st.number_input("Target", 50, 250, 150, 5)
    runs = st.number_input("Current score", 0, target, 45)
    wickets = st.slider("Wickets lost", 0, 10, 2)
    overs = st.slider("Overs bowled", 0.0, 20.0, 6.0, 0.1)

    if st.button("🎯 Update Probability", type="primary", use_container_width=True):
        balls_bowled = int(overs * 6)
        balls_left = 120 - balls_bowled
        runs_needed = target - runs
        wkts_left = 10 - wickets

        if balls_left <= 0 or runs_needed <= 0:
            prob = 1.0 if runs_needed <= 0 else 0.0
        elif wkts_left <= 0:
            prob = 0.0
        else:
            rrr = (runs_needed / balls_left) * 6
            crr = (runs / balls_bowled) * 6 if balls_bowled else 0
            z = 2.0 - 0.6 * rrr + 0.3 * wkts_left + 0.02 * balls_left + 0.3 * crr
            prob = 1 / (1 + pow(2.71828, -z))

        st.metric("Chasing Team Win Probability", f"{prob*100:.1f}%")
        st.progress(prob)
        st.caption(f"RRR: {(runs_needed/balls_left*6):.2f} | "
                   f"Balls left: {balls_left} | Wickets left: {wkts_left}")


# ------------------------------------------
# TAB 3: HISTORY
# ------------------------------------------
with tab3:
    st.subheader("📊 Prediction History")

    if not st.session_state.history:
        st.info("No predictions yet.")
    else:
        resolved = [h for h in st.session_state.history if h["actual"]]
        correct = sum(1 for h in resolved if h["predicted"] == h["actual"])

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Picks", len(st.session_state.history))
        c2.metric("Resolved", len(resolved))
        c3.metric("Accuracy", f"{correct/len(resolved)*100:.1f}%" if resolved else "—")

        st.divider()
        for i, h in enumerate(st.session_state.history):
            with st.expander(f"#{i+1} · {h['team1'][:15]} vs {h['team2'][:15]}"):
                st.write(f"**Predicted:** {h['predicted']} ({h['confidence']})")
                options = ["—", h["team1"], h["team2"]]
                current = h["actual"] if h["actual"] in options else "—"
                choice = st.radio("Actual winner:", options,
                                  index=options.index(current),
                                  key=f"h_{i}", horizontal=True)
                if choice != "—":
                    st.session_state.history[i]["actual"] = choice

                if h["actual"]:
                    if h["predicted"] == h["actual"]:
                        st.success("✅ Correct")
                    else:
                        st.error("❌ Wrong")

        if st.button("🗑️ Clear History"):
            st.session_state.history = []
            st.rerun()


# ------------------------------------------
# TAB 4: CRICSHEET
# ------------------------------------------
with tab4:
    st.subheader("🔄 Cricsheet Auto-Sync")
    st.caption("Download real CPL match results from cricsheet.org")

    if st.button("⬇️ Sync Cricsheet Now", type="primary", use_container_width=True):
        with st.spinner("Downloading..."):
            try:
                df = sync_cricsheet()
                st.session_state.cricsheet_df = df
                st.success(f"✅ Loaded {len(df)} CPL matches")
            except Exception as e:
                st.error(f"Failed: {e}")

    df = st.session_state.cricsheet_df

    if df.empty:
        st.info("Tap **Sync Cricsheet Now** to load data.")
    else:
        st.markdown(f"**{len(df)} matches loaded**")

        # ---- Filter ----
        teams = sorted(set(df["team1"].dropna()) | set(df["team2"].dropna()))
        team_filter = st.selectbox("Filter by team", ["All"] + teams)

        view = df if team_filter == "All" else df[
            (df["team1"] == team_filter) | (df["team2"] == team_filter)
        ]

        st.dataframe(
            view[["date", "team1", "team2", "toss_winner",
                  "toss_decision", "winner", "venue"]],
            use_container_width=True,
            hide_index=True,
        )

        # ---- Download CSV ----
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download CSV", csv, "cricsheet_cpl.csv", "text/csv")
   



