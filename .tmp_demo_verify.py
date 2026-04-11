from datetime import date
from logic.config import LAGOS_AREAS, TOPO_DATA
from logic.streamlit_helpers import fetch_weather
from logic.prediction_logic import load_model, nearest_grid, run_prediction

start = date(2024,7,6)
lat, lon = LAGOS_AREAS['ajah']
weather_df, err, mode = fetch_weather(lat, lon, days=3, start_date=start)
model = load_model()
cell = nearest_grid(lat, lon)
pred = run_prediction(weather_df, TOPO_DATA[cell], model)
print('mode=', mode, 'err=', err, 'grid=', cell)
print(pred[['date','tp_mm','runoff_mm','flood_prob','flood_predicted','risk_level']].to_string(index=False))
