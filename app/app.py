import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import folium
from folium.plugins import HeatMap, MarkerCluster
from streamlit_folium import st_folium
import joblib

# ─── Page config ───────────────────────────────────────────────
st.set_page_config(
    page_title="Road Accident Hotspot Predictor",
    page_icon="🚨",
    layout="wide"
)

# ─── Load data & model ─────────────────────────────────────────
@st.cache_data
def load_data():
    return pd.read_csv('../data/Road.csv')  # Apna filename daalo

@st.cache_resource
def load_model():
    model   = joblib.load('../models/accident_model.pkl')
    columns = joblib.load('../models/feature_columns.pkl')
    return model, columns

df              = load_data()
model, feat_cols = load_model()

# ─── Sidebar filters ───────────────────────────────────────────
st.sidebar.title("🔧 Filters")

weather_options = ['All'] + df['Weather_conditions'].dropna().unique().tolist()
selected_weather = st.sidebar.selectbox("Weather Condition", weather_options)

day_options = ['All'] + df['Day_of_week'].dropna().unique().tolist()
selected_day = st.sidebar.selectbox("Day of Week", day_options)

severity_options = ['All'] + df['Accident_severity'].dropna().unique().tolist()
selected_severity = st.sidebar.selectbox("Accident Severity", severity_options)

# Apply filters
filtered_df = df.copy()
if selected_weather != 'All':
    filtered_df = filtered_df[filtered_df['Weather_conditions'] == selected_weather]
if selected_day != 'All':
    filtered_df = filtered_df[filtered_df['Day_of_week'] == selected_day]
if selected_severity != 'All':
    filtered_df = filtered_df[filtered_df['Accident_severity'] == selected_severity]

# ─── Header ────────────────────────────────────────────────────
st.title("🚨 Road Accident Hotspot Predictor")
st.markdown("**ML-powered dashboard** to analyze and predict road accident severity")
st.divider()

# ─── Metric cards ──────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Accidents",   f"{len(filtered_df):,}")
col2.metric("Fatal Injuries",    f"{(filtered_df['Accident_severity'] == 'Fatal injury').sum():,}")
col3.metric("Serious Injuries",  f"{(filtered_df['Accident_severity'] == 'Serious Injury').sum():,}")
col4.metric("Slight Injuries",   f"{(filtered_df['Accident_severity'] == 'Slight Injury').sum():,}")

st.divider()

# ─── Tabs ──────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 EDA Charts", "🗺️ Hotspot Map", "🤖 Predict Risk"])

# ══════════════════════════════════════════════════════
# TAB 1 — EDA Charts
# ══════════════════════════════════════════════════════
with tab1:
    st.subheader("Exploratory Data Analysis")

    c1, c2 = st.columns(2)

    # Chart 1 — Severity distribution
    with c1:
        st.markdown("**Accident Severity Distribution**")
        fig, ax = plt.subplots(figsize=(6, 4))
        filtered_df['Accident_severity'].value_counts().plot(
            kind='bar', color=['#e74c3c','#f39c12','#2ecc71'], ax=ax
        )
        ax.set_xlabel("Severity"); ax.set_ylabel("Count")
        ax.tick_params(axis='x', rotation=15)
        st.pyplot(fig); plt.close()

    # Chart 2 — Accidents by day
    with c2:
        st.markdown("**Accidents by Day of Week**")
        day_order = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
        day_counts = filtered_df['Day_of_week'].value_counts().reindex(day_order, fill_value=0)
        fig, ax = plt.subplots(figsize=(6, 4))
        day_counts.plot(kind='bar', color='#3498db', ax=ax)
        ax.set_xlabel("Day"); ax.set_ylabel("Count")
        ax.tick_params(axis='x', rotation=30)
        st.pyplot(fig); plt.close()

    c3, c4 = st.columns(2)

    # Chart 3 — Weather vs Severity heatmap
    with c3:
        st.markdown("**Weather vs Accident Severity**")
        ct = pd.crosstab(filtered_df['Weather_conditions'],
                         filtered_df['Accident_severity'])
        fig, ax = plt.subplots(figsize=(6, 4))
        sns.heatmap(ct, annot=True, fmt='d', cmap='YlOrRd', ax=ax)
        ax.tick_params(axis='x', rotation=15)
        st.pyplot(fig); plt.close()

    # Chart 4 — Top causes
    with c4:
        st.markdown("**Top 10 Causes of Accidents**")
        fig, ax = plt.subplots(figsize=(6, 4))
        filtered_df['Cause_of_accident'].value_counts().head(10).plot(
            kind='barh', color='#8e44ad', ax=ax
        )
        ax.set_xlabel("Count")
        st.pyplot(fig); plt.close()

# ══════════════════════════════════════════════════════
# TAB 2 — Hotspot Map
# ══════════════════════════════════════════════════════
with tab2:
    st.subheader("Accident Hotspot Heatmap")
    st.caption("Redder zones = higher accident frequency")

    area_coords = {
        'Other':                (9.00, 38.70),
        'Office areas':         (9.02, 38.75),
        'Residential areas':    (8.98, 38.68),
        'Church areas':         (9.05, 38.72),
        'Industrial areas':     (8.95, 38.65),
        'School areas':         (9.01, 38.80),
        'Recreational areas':   (9.08, 38.78),
        'Outside Addis Ababa':  (8.50, 38.20),
        'Hospital areas':       (9.03, 38.71),
        'Market areas':         (9.00, 38.74),
        'Rural village areas':  (8.70, 38.50),
        'Unknown':              (9.00, 38.70),
    }

    area_counts = (
        filtered_df['Area_accident_occured']
        .value_counts()
        .reset_index()
    )
    area_counts.columns = ['Area', 'Count']
    area_counts['lat'] = area_counts['Area'].map(lambda x: area_coords.get(x, (9.0, 38.7))[0])
    area_counts['lng'] = area_counts['Area'].map(lambda x: area_coords.get(x, (9.0, 38.7))[1])

    m = folium.Map(location=[9.0, 38.7], zoom_start=12)

    heat_data = []
    for _, row in area_counts.iterrows():
        for _ in range(row['Count']):
            heat_data.append([
                row['lat'] + np.random.uniform(-0.01, 0.01),
                row['lng'] + np.random.uniform(-0.01, 0.01)
            ])

    HeatMap(heat_data, radius=25, blur=15, min_opacity=0.4).add_to(m)
    mc = MarkerCluster().add_to(m)

    for _, row in area_counts.iterrows():
        folium.CircleMarker(
            location=[row['lat'], row['lng']],
            radius=max(5, row['Count'] / 50),
            color='red', fill=True, fill_opacity=0.7,
            popup=folium.Popup(
                f"<b>{row['Area']}</b><br>Accidents: {row['Count']}",
                max_width=200
            )
        ).add_to(mc)

    st_folium(m, width=900, height=500)

# ══════════════════════════════════════════════════════
# TAB 3 — Live Prediction
# ══════════════════════════════════════════════════════
with tab3:
    st.subheader("Predict Accident Severity")
    st.caption("Fill in the details below to get a risk prediction")

    p1, p2, p3 = st.columns(3)

    with p1:
        hour           = st.slider("Hour of Day", 0, 23, 12)
        day_of_week    = st.selectbox("Day of Week",
                             ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'])
        weather        = st.selectbox("Weather Conditions",
                             df['Weather_conditions'].dropna().unique().tolist())

    with p2:
        num_vehicles   = st.slider("Number of Vehicles Involved", 1, 10, 2)
        num_casualties = st.slider("Number of Casualties", 1, 10, 1)
        road_surface   = st.selectbox("Road Surface Type",
                             df['Road_surface_type'].dropna().unique().tolist())

    with p3:
        light_cond     = st.selectbox("Light Conditions",
                             df['Light_conditions'].dropna().unique().tolist())
        cause          = st.selectbox("Cause of Accident",
                             df['Cause_of_accident'].dropna().unique().tolist())
        junction_type  = st.selectbox("Type of Junction",
                             df['Types_of_Junction'].dropna().unique().tolist())

    if st.button("🔍 Predict Risk", use_container_width=True):

        from sklearn.preprocessing import LabelEncoder

        # Build input row with all feature columns (zeros default)
        input_data = pd.DataFrame(columns=feat_cols)
        input_data.loc[0] = 0

        # Map user inputs
        input_map = {
            'Hour':                        hour,
            'Number_of_vehicles_involved': num_vehicles,
            'Number_of_casualties':        num_casualties,
        }

        # Encode categorical inputs using training data mode as reference
        cat_map = {
            'Day_of_week':          day_of_week,
            'Weather_conditions':   weather,
            'Road_surface_type':    road_surface,
            'Light_conditions':     light_cond,
            'Cause_of_accident':    cause,
            'Types_of_Junction':    junction_type,
        }

        temp_df = df.copy()
        le = LabelEncoder()
        for col, val in cat_map.items():
            if col in feat_cols:
                le.fit(temp_df[col].astype(str))
                try:
                    encoded = le.transform([str(val)])[0]
                except:
                    encoded = 0
                input_map[col] = encoded

        for col, val in input_map.items():
            if col in feat_cols:
                input_data[col] = val

        input_data = input_data.fillna(0)

        prediction   = model.predict(input_data)[0]
        proba        = model.predict_proba(input_data)[0]
        confidence   = round(max(proba) * 100, 1)

        # Display result
        st.divider()
        if prediction == 0 or 'Fatal' in str(prediction):
            st.error(f"🔴 **Fatal Injury Risk** — Confidence: {confidence}%")
            st.warning("Extremely high-risk conditions. Avoid travel if possible.")
        elif prediction == 1 or 'Serious' in str(prediction):
            st.warning(f"🟠 **Serious Injury Risk** — Confidence: {confidence}%")
            st.info("High-risk conditions. Drive with extra caution.")
        else:
            st.success(f"🟢 **Slight Injury Risk** — Confidence: {confidence}%")
            st.info("Moderate risk. Standard precautions recommended.")

        # Probability bar
        st.markdown("**Risk probability breakdown:**")
        classes = model.classes_
        for cls, prob in zip(classes, proba):
            st.progress(float(prob), text=f"{cls}: {round(prob*100, 1)}%")