from datetime import date
from logic.config import LAGOS_AREAS, TOPO_DATA
from logic.streamlit_helpers import fetch_weather
from logic.prediction_logic import load_model, nearest_grid, run_prediction

areas = ["ajah", "lekki", "apapa", "victoria island", "ikeja"]
dates = [
    date(2023,7,8), date(2023,7,15), date(2023,9,16),
    date(2024,6,22), date(2024,7,6), date(2024,7,13), date(2024,9,14),
    date(2025,6,21), date(2025,7,12), date(2025,8,2)
]

model = load_model()
rows = []
for d in dates:
    for area in areas:
        lat, lon = LAGOS_AREAS[area]
        try:
            weather_df, err, mode = fetch_weather(lat, lon, days=3, start_date=d)
            if err or weather_df is None:
                rows.append((d.isoformat(), area, -1, -1, -1, "ERR"))
                continue
            cell = nearest_grid(lat, lon)
            pred = run_prediction(weather_df, TOPO_DATA[cell], model)
            max_prob = float(pred['flood_prob'].max())
            flood_days = int(pred['flood_predicted'].sum())
            rain3d = float(pred['tp_mm'].sum())
            rows.append((d.isoformat(), area, max_prob, flood_days, rain3d, mode))
        except Exception:
            rows.append((d.isoformat(), area, -1, -1, -1, "EXC"))

rows = [r for r in rows if r[2] >= 0]
rows.sort(key=lambda x: (x[2], x[3], x[4]), reverse=True)
print('Top candidates:')
for r in rows[:15]:
    print(f"date={r[0]} area={r[1]:15s} max_prob={r[2]:.3f} flood_days={r[3]} rain3d={r[4]:.1f} mode={r[5]}")

print('\nBest per date:')
for d in sorted(set([x[0] for x in rows])):
    day = [x for x in rows if x[0]==d]
    b = sorted(day, key=lambda x: (x[2], x[3], x[4]), reverse=True)[0]
    print(f"date={d} best_area={b[1]} max_prob={b[2]:.3f} flood_days={b[3]} rain3d={b[4]:.1f}")
