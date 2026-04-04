from __future__ import annotations

import os
from datetime import date, timedelta

import streamlit as st
from dotenv import load_dotenv

from logic.config import APP_NAME, LOGO, GRID_CELLS, LAGOS_AREAS, TOPO_DATA
from logic.streamlit_helpers import (
    build_context,
    fetch_weather,
    groq_chat,
)
from logic.prediction_logic import load_model, nearest_grid, run_prediction
from logic.streamlit_ui import (
    auto_fetch_location,
    chat_bubble,
    divider,
    ensure_session_state,
    forecast_cards,
    inject_styles,
    render_header,
    risk_banner,
    section_label,
)


st.set_page_config(
    page_title=APP_NAME,
    page_icon=str(LOGO) if LOGO.exists() else "No logo",
    layout="wide",
    initial_sidebar_state="collapsed",
)

load_dotenv()

ensure_session_state()
inject_styles(st.session_state.dark)

model = load_model()

render_header(LOGO)
divider()

today = date.today()
if "forecast_start_date" not in st.session_state:
    st.session_state.forecast_start_date = today

section_label("Enter Date")

forecast_start_date = st.date_input(
    "Enter Date",
    value=st.session_state.forecast_start_date,
    label_visibility="collapsed",
    key="forecast_start_date",
    help="Pick any date to start the 3-day prediction window.",
)

forecast_horizon = today + timedelta(days=16)
if forecast_start_date > forecast_horizon:
    st.warning(
        "This date is beyond the normal forecast window. FloodIQ will use a climatology estimate instead of a real forecast."
    )

section_label("User Location")
loc_col = st.columns([1])[0]
lat, lon, location_name = None, None, None
area_lat, area_lon, area_name = None, None, None
manual_lat, manual_lon, manual_name = None, None, None
auto_lat, auto_lon, auto_name = None, None, None

with loc_col:
    tab1, tab2, tab3 = st.tabs(["Area Name  ", "Coordinates  ", "Auto Detect  "])

    with tab1:
        area_input = st.text_input(
            "Lagos area",
            placeholder="Ikeja, Lekki, VI, Surulere, Yaba...",
            label_visibility="collapsed",
            key="area_in",
        )
        if area_input:
            key = area_input.lower().strip()
            match = LAGOS_AREAS.get(key)
            if not match:
                for area_name, coordinates in LAGOS_AREAS.items():
                    if key in area_name or area_name in key:
                        match = coordinates
                        break
            if match:
                area_lat, area_lon = match
                area_name = area_input.title()
                st.success(f"Found {area_name}  ({area_lat}, {area_lon})")
            else:
                st.warning("Area not found - try: Ikeja, Lekki, VI, Surulere, Yaba, Ikorodu, Apapa...")

    with tab2:
        first_column, second_column = st.columns(2)
        with first_column:
            manual_lat = st.number_input(
                "Lat",
                value=6.55,
                min_value=6.25,
                max_value=6.85,
                step=0.01,
            )
        with second_column:
            manual_lon = st.number_input(
                "Lon",
                value=3.25,
                min_value=2.95,
                max_value=3.55,
                step=0.01,
            )
        manual_name = f"({manual_lat:.3f}°N, {manual_lon:.3f}°E)"

    with tab3:
        auto_lat, auto_lon, auto_name = auto_fetch_location()

if auto_lat is not None and auto_lon is not None:
    lat, lon, location_name = auto_lat, auto_lon, auto_name
elif area_lat is not None and area_lon is not None:
    lat, lon, location_name = area_lat, area_lon, area_name
elif manual_lat is not None and manual_lon is not None:
    lat, lon, location_name = manual_lat, manual_lon, manual_name

divider()

if model is None:
    st.error("Model file not found. Place xgb_cw_model.pkl in the model folder.")
    st.stop()

predict_btn = False
if st.session_state.predictions is None:
    button_left, button_center, button_right = st.columns([1, 2, 1])
    with button_center:
        predict_btn = st.button(
            "Get Risk Prediction",
            use_container_width=True,
            disabled=(lat is None),
        )

if predict_btn and lat is not None:
    dot_color = "#29D4B0" if st.session_state.dark else "#0A8F7A"

    def loader_html(message: str) -> str:
        return f"""
        <style>
          @keyframes floodiq-bounce {{
            0%, 80%, 100% {{ transform: scale(0); opacity: 0.4; }}
            40% {{ transform: scale(1); opacity: 1; }}
          }}
        </style>
        <div style="display:flex;align-items:center;justify-content:center;gap:10px;padding:10px 0 18px 0;">
          <span style="font-size:0.88rem;opacity:0.85;">{message}</span>
          <div style="display:flex;align-items:center;gap:6px;">
            <span style="width:8px;height:8px;border-radius:50%;display:inline-block;background:{dot_color};animation:floodiq-bounce 1.4s infinite ease-in-out both;animation-delay:-0.32s;"></span>
            <span style="width:8px;height:8px;border-radius:50%;display:inline-block;background:{dot_color};animation:floodiq-bounce 1.4s infinite ease-in-out both;animation-delay:-0.16s;"></span>
            <span style="width:8px;height:8px;border-radius:50%;display:inline-block;background:{dot_color};animation:floodiq-bounce 1.4s infinite ease-in-out both;"></span>
          </div>
        </div>
        """

    weather_loading = st.empty()
    weather_loading.markdown(loader_html("Fetching weather data"), unsafe_allow_html=True)
    weather_df, error, weather_mode = fetch_weather(lat, lon, days=3, start_date=forecast_start_date)
    weather_loading.empty()

    if error:
        st.error(f"Weather API error: {error}")
    else:
        if weather_mode == "climatology":
            st.info("The selected date is beyond the normal forecast window, so FloodIQ is using a historical climatology estimate.")
        elif weather_mode == "archive":
            st.info("The selected date is in the past, so FloodIQ is using archived weather data.")

        model_loading = st.empty()
        model_loading.markdown(loader_html("Running model prediction"), unsafe_allow_html=True)
        grid_cell = nearest_grid(lat, lon)
        topo = TOPO_DATA[grid_cell]
        predictions = run_prediction(weather_df, topo, model)
        context = build_context(predictions, location_name, lat, lon, grid_cell)
        model_loading.empty()

        st.session_state.predictions = predictions
        st.session_state.pred_context = context
        st.session_state.location_name = location_name
        st.session_state.selected_lat = lat
        st.session_state.selected_lon = lon
        st.session_state.chat_history = []
        st.rerun()

if st.session_state.predictions is not None:
    predictions = st.session_state.predictions
    if "followup_input" not in st.session_state:
        st.session_state.followup_input = ""
    if "followup_pending" not in st.session_state:
        st.session_state.followup_pending = ""

    display_location = st.session_state.location_name or location_name
    display_lat = st.session_state.selected_lat if st.session_state.selected_lat is not None else lat
    display_lon = st.session_state.selected_lon if st.session_state.selected_lon is not None else lon

    grid_cell = nearest_grid(display_lat or 6.55, display_lon or 3.25)
    topo = TOPO_DATA[grid_cell]
    colors = st.session_state.dark and {
        "SURFACE2": "#1A2540",
        "BORDER": "#1E3050",
        "ACCENT": "#29D4B0",
        "TEXT2": "#9DB4D4",
    } or {
        "SURFACE2": "#E8F2FF",
        "BORDER": "#C8DCEF",
        "ACCENT": "#0A8F7A",
        "TEXT2": "#3A5068",
    }

    st.markdown(
        f"""
    <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px;">
      <span style="background:{colors['SURFACE2']};border:1px solid {colors['BORDER']};
                   border-radius:999px;padding:5px 13px;
                   font-family:'DM Mono',monospace;font-size:0.78rem;
                   color:{colors['ACCENT']};">📍 {display_location}</span>
      <span style="background:{colors['SURFACE2']};border:1px solid {colors['BORDER']};
                   border-radius:999px;padding:5px 13px;
                   font-family:'DM Mono',monospace;font-size:0.78rem;
                   color:{colors['TEXT2']};">Grid {grid_cell[0]}°N {grid_cell[1]}°E</span>
      <span style="background:{colors['SURFACE2']};border:1px solid {colors['BORDER']};
                   border-radius:999px;padding:5px 13px;
                   font-family:'DM Mono',monospace;font-size:0.78rem;
                   color:{colors['TEXT2']};">⬆ {topo['elevation']}m elev.</span>
    </div>
    """,
        unsafe_allow_html=True,
    )

    section_label("3-Day Flood Forecast")
    flood_days = int(predictions["flood_predicted"].sum())
    risk_banner(flood_days)
    forecast_cards(predictions)

    divider()

    section_label("AI Risk Assistant")
    colors = st.session_state.dark and {
        "H_COLOR": "#E8F0FE",
        "SURFACE2": "#1A2540",
        "BORDER": "#1E3050",
        "TEXT2": "#9DB4D4",
    } or {
        "H_COLOR": "#0D1B2A",
        "SURFACE2": "#E8F2FF",
        "BORDER": "#C8DCEF",
        "TEXT2": "#3A5068",
    }
    st.markdown(f"<h3 style='margin-top:4px;color:{colors['H_COLOR']};'> Ask FloodIQ AI</h3>", unsafe_allow_html=True)

    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        groq_key = st.secrets.get("GROQ_API_KEY", "")
    groq_ok = bool(groq_key)

    if not groq_ok:
        st.markdown(
            f"""
        <div style="background:{colors['SURFACE2']};border:1.5px solid {colors['BORDER']};
                    border-radius:10px;padding:14px 18px;
                    font-size:0.9rem;color:{colors['TEXT2']};">
          Add GROQ_API_KEY to .streamlit/secrets.toml or .env
          - use the key from console.groq.com
        </div>
        """,
            unsafe_allow_html=True,
        )
    else:
        def queue_followup_question():
            draft = st.session_state.followup_input.strip()
            if draft:
                st.session_state.followup_pending = draft
                st.session_state.followup_input = ""

        if len(st.session_state.chat_history) == 0:
            init_prompt = (
                f"Explain the flood forecast for {display_location} in plain English. "
                f"What should residents know and do? Be concise and practical."
            )
            st.session_state.chat_history.append({"role": "user", "content": init_prompt})

            with st.spinner("AI is analysing your forecast..."):
                response, error = groq_chat(
                    groq_key,
                    st.session_state.chat_history,
                    st.session_state.pred_context,
                )
            if error:
                st.error(error)
                st.session_state.chat_history = []
            else:
                st.session_state.chat_history.append({"role": "assistant", "content": response})

        for index, message in enumerate(st.session_state.chat_history):
            if index == 0 and message["role"] == "user":
                continue
            chat_bubble(message["role"], message["content"])

        st.text_input(
            "Ask a follow-up question",
            placeholder="Ask about flood risk, safety tips, evacuation routes... (Press Enter)",
            key="followup_input",
            label_visibility="collapsed",
            on_change=queue_followup_question,
        )

        pending_question = st.session_state.followup_pending.strip()
        if pending_question:
            st.session_state.chat_history.append({"role": "user", "content": pending_question})
            st.session_state.followup_pending = ""

            with st.spinner("Thinking..."):
                response, error = groq_chat(
                    groq_key,
                    st.session_state.chat_history,
                    st.session_state.pred_context,
                )
            if error:
                st.error(error)
            else:
                st.session_state.chat_history.append({"role": "assistant", "content": response})
                st.rerun()

    divider()

    reset_left, reset_center, reset_right = st.columns([1, 2, 1])
    with reset_center:
        if st.button("New Prediction", use_container_width=True):
            st.session_state.predictions = None
            st.session_state.chat_history = []
            st.session_state.pred_context = ""
            st.session_state.location_name = ""
            st.session_state.selected_lat = None
            st.session_state.selected_lon = None
            st.session_state.forecast_start_date = today
            st.rerun()
else:
    colors = st.session_state.dark and {
        "ACCENT": "#29D4B0",
        "TEXT3": "#5A7A9E",
    } or {
        "ACCENT": "#0A8F7A",
        "TEXT3": "#7A9AB8",
    }
    st.markdown(
        f"""
    <div style="text-align:center;padding:50px 20px;">
      <div style="font-family:'DM Mono',monospace;font-size:1rem;
                  color:{colors['ACCENT']};font-weight:600;letter-spacing:0.04em;">
        Select a location above and click Get Flood Forecast
      </div>
      <div style="font-size:0.9rem;color:{colors['TEXT3']};margin-top:12px;
                  max-width:480px;margin-left:auto;margin-right:auto;
                  line-height:1.6;">
        FloodIQ fetches real-time weather data and runs an XGBoost classifier
        trained on ERA5 reanalysis data to predict flood risk for Lagos State.
      </div>
    </div>
    """,
        unsafe_allow_html=True,
    )
