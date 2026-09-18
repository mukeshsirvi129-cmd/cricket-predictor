import streamlit as st

st.set_page_config(page_title="CPL Predictor", page_icon="🏏")

st.title("🏏 CPL Match Predictor")
st.caption("Simple version — works from your phone")

# ---- Inputs ----
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

# ---- Predict ----
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

    total = s1 + s2
    p1 = s1 / total * 100
    p2 = s2 / total * 100

    winner = team1 if p1 > p2 else team2
    diff = abs(p1 - p2)

    if diff >= 25:
        conf = "🔒 HIGH"
    elif diff >= 15:
        conf = "✅ MEDIUM-HIGH"
    elif diff >= 8:
        conf = "⚠️ MEDIUM"
    else:
        conf = "🤔 LOW"

    st.success(f"🏆 Predicted Winner: **{winner}**")
    st.metric(team1, f"{p1:.1f}%")
    st.metric(team2, f"{p2:.1f}%")
    st.info(f"Confidence: {conf}")