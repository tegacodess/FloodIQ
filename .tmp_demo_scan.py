from datetime import date, timedelta
from logic.config import LAGOS_AREAS, TOPO_DATA
from logic.streamlit_helpers import fetch_weather
from logic.prediction_logic import load_model, nearest_grid, run_prediction

areas = ["ajah", "lekki", "apapa", "victoria island", "surulere", "ikorodu"]
end = date.today() - timedelta(days=1)
start = end - timedelta(days=540)

model = load_model()
rows = []

d = start
while d <= end:
    for area in areas:
        lat, lon = LAGOS_AREAS[area]
        weather_df, err, mode = fetch_weather(lat, lon, days=3, start_date=d)
        if err or weather_df is None:
            continue
        cell = nearest_grid(lat, lon)
        pred = run_prediction(weather_df, TOPO_DATA[cell], model)
        max_prob = float(pred["flood_prob"].max())
        flood_days = int(pred["flood_predicted"].sum())
        rain_total = float(pred["tp_mm"].sum())
        rows.append((max_prob, flood_days, rain_total, d.isoformat(), area, mode))
    d += timedelta(days=7)

rows.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
print("Top 12 weekly candidates:")
for r in rows[:12]:
    print(f"date={r[3]} area={r[4]:15s} max_prob={r[0]:.3f} flood_days={r[1]} rain3d={r[2]:.1f} mode={r[5]}")
