import numpy as np
import pandas as pd
import joblib
from .config import FEATURE_COLS, GRID_CELLS, STREAMLIT_MODEL

def load_model(model_path=STREAMLIT_MODEL):
    return joblib.load(model_path)

def nearest_grid(lat, lon):
    return min(GRID_CELLS, key=lambda c: (c[0]-lat)**2 + (c[1]-lon)**2)

def run_prediction(weather_df, topo, model, threshold=0.5):
    df = weather_df.copy()
    df["elevation"] = topo["elevation"]
    df["slope"] = topo["slope"]
    df["flow_accum"] = topo["flow_accum"]

    probs = model.predict_proba(df[FEATURE_COLS])[:, 1]
    
    # Precipitation guard
    probs = np.where(df["tp"] < 1.0, probs * 0.1, probs)
    df["flood_prob"] = probs
    df["flood_predicted"] = (probs >= threshold).astype(int)

    def get_risk(p):
        if p >= 0.7: return "HIGH", "🔴"
        if p >= 0.4: return "MODERATE", "🟡"
        return "LOW", "🟢"

    df[["risk_level","risk_emoji"]] = df["flood_prob"].apply(lambda p: pd.Series(get_risk(p)))
    return df