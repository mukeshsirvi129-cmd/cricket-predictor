import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from pathlib import Path

st.set_page_config(page_title="CPL Predictor", page_icon="🏏")

st.title("🏏 CPL Match Predictor")
st.caption("Context-first prediction with backtest tracking")

# ============================================
# DATABASE
# ============================================
DB = Path("predictions.db")

def init_db():
    conn = sqlite3.connect(DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            team1 TEXT, team2 TEXT,
            toss_winner TEXT, toss_decision TEXT,
            pitch_type TEXT, dew INTEGER,
            prob_team1 REAL, prob_team2 REAL,
            predicted_winner TEXT, confidence TEXT,
            actual_winner TEXT DEFAULT NULL
        )
    """)
    conn.commit()
    conn.close()

def save_prediction(row):
    conn = sqlite3.connect(DB)
    conn.execute("""
        INSERT INTO predictions
        (timestamp, team1, team2, toss_winner, toss_decision, pitch_type, dew,
         prob_team1, prob_team2, predicted_winner, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(), row["team1"], row["team2"],
        row["toss_winner"], row["toss_decision"], row["pitch_type"],
        int(row["dew"]), row["prob_team1"], row["prob_team2"],
        row["predicted_winner"], row["confidence"],
    ))
    conn.commit()
    conn.close()

def load_predictions():
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query("SELECT * FROM predictions ORDER BY id DESC", conn)
    conn.close()
    return df

def update_actual(pred_id, actual):
    conn = sqlite3.connect(DB)
    conn.execute("UPDATE predictions SET actual_winner = ? WHERE id = ?", (actual, pred_id))
    conn.commit()
    conn.close()

init_db()


# ============================================
# INPUTS
# ============================================
team1 = st.text_input("Team 1", "Guyana Amazon Warriors")
team2 = st.text_input("Team 2", "Antigua and Barbuda Falcons")

toss_winner = st.selectbox("Toss winner", [team1, team2])
toss_decision = st.selectbox("Decision", ["Bowl", "Bat"])

pitch_type = st.selectbox("Pitch type", ["Spin", "Pace", "Flat", "Neutral"])
chase_win_pct = st.slider("Chase win %", 0.0, 1.0, 0.5, 0.05)
dew = st.checkbox("Dew expected?")

spin1 = st.slider(f"{team1} spinners", 0, 6, 3)
spin2 = st.slider(f"{team2} spinners", 0, 6, 4)
form1 = st.slider(f"{team1} wins (last 5)", 0, 5, 2)
form2 = st.slider(f"{team2} wins (last 5)", 0, 5, 4)


# ============================================
# PREDICT
# ============================================
if st.button("🔮 Predict Winner", type="primary"):

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
    elif pitch_type == "Pace":
        if form1 > form2:
            s1 += 0.3
        elif form2 > form1:
            s2 += 0.3

    if dew and chase_win_pct > 0.6:
        if toss_winner == team1 and toss_decision == "Bowl":
            s1 -= 0.3
        elif toss_winner == team2 and toss_decision == "Bowl":
            s2 -= 0.3

    total = s1 + s2
    p1 = s1 / total * 100
    p2 = s2 / total * 100

    winner = team1 if p1 > p2 else team2
    wpct = max(p1, p2)
    lpct = min(p1, p2)
    diff = wpct - lpct

    if diff >= 25:
        conf = "🔒 HIGH"
        msg = "Strong edge. Trust this pick."
    elif diff >= 15:
        conf = "✅ MEDIUM-HIGH"
        msg = "Clear favorite."
    elif diff >= 8:
        conf = "⚠️ MEDIUM"
        msg = "Slight edge."
    else:
        conf = "🤔 LOW"
        msg = "Too close to call."

    st.success(f"🏆 Predicted Winner: **{winner}**")
    st.metric(team1, f"{p1:.1f}%")
    st.metric(team2, f"{p2:.1f}%")
    st.info(f"Confidence: **{conf}** — {msg}")

    save_prediction({
        "team1": team1, "team2": team2,
        "toss_winner": toss_winner, "toss_decision": toss_decision,
        "pitch_type": pitch_type, "dew": dew,
        "prob_team1": p1, "prob_team2": p2,
        "predicted_winner": winner, "confidence": conf,
    })
    st.caption("✅ Saved to history")


# ============================================
# HISTORY + ACCURACY
# ============================================
st.divider()
st.subheader("📊 Prediction History & Accuracy")

df = load_predictions()

if df.empty:
    st.info("No predictions yet. Make one above.")
else:
    # ---- Accuracy metrics ----
    resolved = df[df["actual_winner"].notna()]
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Picks", len(df))
    col2.metric("Resolved", len(resolved))
    
    if not resolved.empty:
        correct = (resolved["predicted_winner"] == resolved["actual_winner"]).sum()
        acc = correct / len(resolved) * 100
        col3.metric("Accuracy", f"{acc:.1f}%", f"{correct}/{len(resolved)}")
    else:
        col3.metric("Accuracy", "—")

    # ---- Confidence calibration ----
    if not resolved.empty:
        st.markdown("#### 🎯 Accuracy by Confidence Level")
        resolved = resolved.copy()
        resolved["correct"] = (resolved["predicted_winner"] == resolved["actual_winner"]).astype(int)

        conf_stats = resolved.groupby("confidence").agg(
            total=("id", "count"),
            correct=("correct", "sum"),
        ).reset_index()
        conf_stats["accuracy"] = (conf_stats["correct"] / conf_stats["total"] * 100).round(1)

        st.dataframe(conf_stats, use_container_width=True, hide_index=True)

    # ---- Update actual winner ----
    st.markdown("#### ✏️ Mark Actual Winner")
    st.caption("Tap a match below to record the actual result.")

    for _, row in df.head(10).iterrows():
        with st.expander(f"#{row['id']} · {row['team1'][:15]} vs {row['team2'][:15]}"):
            st.write(f"**Predicted:** {row['predicted_winner']}")
            st.write(f"**Confidence:** {row['confidence']}")
            st.write(f"**Probabilities:** {row['prob_team1']:.1f}% vs {row['prob_team2']:.1f}%")

            options = ["—", row["team1"], row["team2"]]
            current = row["actual_winner"] if row["actual_winner"] in options else "—"
            choice = st.radio(
                "Actual winner:",
                options,
                index=options.index(current),
                key=f"act_{row['id']}",
                horizontal=True,
            )

            if choice != "—" and choice != row["actual_winner"]:
                update_actual(row["id"], choice)
                st.rerun()

            if row["actual_winner"]:
                correct = row["predicted_winner"] == row["actual_winner"]
                if correct:
                    st.success("✅ Correct prediction")
                else:
                    st.error("❌ Wrong prediction")

    # ---- Full history table ----
    st.markdown("#### 📋 Full History")
    st.dataframe(
        df[["id", "timestamp", "team1", "team2", "predicted_winner",
            "actual_winner", "confidence"]],
        use_container_width=True,
        hide_index=True,
    )