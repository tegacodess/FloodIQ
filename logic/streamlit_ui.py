from __future__ import annotations

import json
import streamlit as st

try:
    from streamlit_js_eval import get_geolocation
except ImportError:
    get_geolocation = None

from logic.config import LAGOS_AREAS


def ensure_session_state():
    if "dark" not in st.session_state:
        st.session_state.dark = False
    if "predictions" not in st.session_state:
        st.session_state.predictions = None
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "pred_context" not in st.session_state:
        st.session_state.pred_context = ""
    if "location_name" not in st.session_state:
        st.session_state.location_name = ""
    if "selected_lat" not in st.session_state:
        st.session_state.selected_lat = None
    if "selected_lon" not in st.session_state:
        st.session_state.selected_lon = None
    if "geolocation_lat" not in st.session_state:
        st.session_state.geolocation_lat = None
    if "geolocation_lon" not in st.session_state:
        st.session_state.geolocation_lon = None
    if "geolocation_device_requested" not in st.session_state:
        st.session_state.geolocation_device_requested = False
    if "geolocation_error" not in st.session_state:
        st.session_state.geolocation_error = ""


def get_theme(dark: bool):
    if dark:
        return {
            "BG": "#0B1120",
            "SURFACE": "#131C2E",
            "SURFACE2": "#1A2540",
            "TEXT": "#E8F0FE",
            "TEXT2": "#9DB4D4",
            "TEXT3": "#5A7A9E",
            "ACCENT": "#29D4B0",
            "ACCENT2": "#4A9EFF",
            "RED": "#FF6B6B",
            "AMBER": "#FFB547",
            "GREEN": "#3DDC84",
            "BORDER": "#1E3050",
            "CARD_FLOOD": "#1A1030",
            "H_COLOR": "#E8F0FE",
        }
    return {
        "BG": "#F0F7FF",
        "SURFACE": "#FFFFFF",
        "SURFACE2": "#E8F2FF",
        "TEXT": "#0D1B2A",
        "TEXT2": "#3A5068",
        "TEXT3": "#7A9AB8",
        "ACCENT": "#0A8F7A",
        "ACCENT2": "#1A6FD4",
        "RED": "#D94040",
        "AMBER": "#D97706",
        "GREEN": "#1A8C4E",
        "BORDER": "#C8DCEF",
        "CARD_FLOOD": "#FFF0F0",
        "H_COLOR": "#0D1B2A",
    }


def inject_styles(dark: bool):
    colors = get_theme(dark)
    popup_bg = "#121A2A"
    popup_border = "#2B3954"
    popup_text = "#F1F6FF"
    st.markdown(
        f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700;800&family=DM+Mono:wght@400;500&display=swap');

  html, body, [class*="css"] {{
    font-family: 'Syne', sans-serif;
    background-color: {colors['BG']} !important;
    color: {colors['TEXT']} !important;
  }}

  #MainMenu, footer, header {{ visibility: hidden; }}
  .stDeployButton {{ display: none; }}

  .main .block-container {{
    max-width: 980px !important;
    padding: 2rem 2rem 4rem 2rem !important;
  }}

  .stApp {{ background-color: {colors['BG']} !important; }}

  h1, h2, h3, h4 {{
    font-family: 'Syne', sans-serif !important;
    color: {colors['H_COLOR']} !important;
    font-weight: 800 !important;
  }}

  p, div, span, label {{
    color: {colors['TEXT']};
    font-family: 'Syne', sans-serif;
  }}

  /* --- Inputs --- */
  .stTextInput > div > div > input,
  .stNumberInput > div > div > input,
  .stDateInput > div > div > input,
  .stSelectbox > div > div {{
        background: {'#FFFFFF' if not dark else colors['SURFACE']} !important;
    color: {colors['TEXT']} !important;
    border: 1.5px solid {colors['BORDER']} !important;
    border-radius: 10px !important;
    font-family: 'Syne', sans-serif !important;
  }}
  .stDateInput {{
      background: transparent !important;
  }}
  .stDateInput [data-baseweb="base-input"],
  .stDateInput [data-baseweb="input"],
  .stDateInput [data-baseweb="input"] > div,
  .stDateInput [data-baseweb="input"] > div > div {{
      background: {'#FFFFFF' if not dark else colors['SURFACE']} !important;
      border-color: {colors['BORDER']} !important;
      border-radius: 10px !important;
      box-shadow: none !important;
  }}
  .stDateInput input {{
      background: transparent !important;
      color: {colors['TEXT']} !important;
  }}
  .stDateInput button {{
      background: {'#FFFFFF' if not dark else colors['SURFACE']} !important;
      color: {colors['TEXT2']} !important;
      border-left: 1px solid {colors['BORDER']} !important;
      border-radius: 0 10px 10px 0 !important;
      box-shadow: none !important;
  }}

  /* --- CALENDAR POPUP FIX --- */
  /* This ensures the actual floating calendar background is dynamic */
  div[data-baseweb="popover"] {{
      background-color: transparent !important;
  }}

  div[data-baseweb="calendar"] {{
      background-color: {popup_bg} !important;
      background: {popup_bg} !important;
      border: 1px solid {popup_border} !important;
      border-radius: 12px !important;
  }}

  /* Fixes the header area of the calendar popover */
  div[data-baseweb="calendar"] > div {{
      background-color: {popup_bg} !important;
  }}

  /* Text colors inside the calendar */
  div[data-baseweb="calendar"] * {{
      color: {popup_text} !important;
      font-family: 'Syne', sans-serif !important;
  }}

  /* Days of the week header */
  div[role="grid"] [role="gridcell"] {{
      background-color: transparent !important;
  }}

  /* Hover states for days */
  div[data-baseweb="calendar"] [role="gridcell"] button:hover {{
      background: #243148 !important;
  }}

  /* Selected date */
  div[data-baseweb="calendar"] [aria-selected="true"] {{
      background: {colors['ACCENT']} !important;
      color: #ffffff !important;
  }}

    div[data-baseweb="calendar"] [aria-disabled="true"],
    div[data-baseweb="calendar"] [aria-disabled="true"] * {{
            color: #9AA9C2 !important;
    }}

    div[data-baseweb="calendar"] button:focus,
    div[data-baseweb="calendar"] button:focus-visible {{
            outline: none !important;
            box-shadow: 0 0 0 2px {colors['ACCENT']}55 !important;
    }}

  /* React DatePicker fallback (if used) */
  .react-datepicker,
  .react-datepicker__header,
  .react-datepicker__month-container {{
      background: {popup_bg} !important;
      background-color: {popup_bg} !important;
      border-color: {popup_border} !important;
  }}

  .react-datepicker__current-month, 
  .react-datepicker__day-name, 
  .react-datepicker__day {{
      color: {popup_text} !important;
  }}

  .react-datepicker__day:hover,
  .react-datepicker__month-text:hover,
  .react-datepicker__quarter-text:hover,
  .react-datepicker__year-text:hover {{
      background: #243148 !important;
      color: {popup_text} !important;
  }}

  .react-datepicker__day--selected,
  .react-datepicker__day--keyboard-selected {{
      background: {colors['ACCENT']} !important;
      color: #ffffff !important;
  }}

  /* --- Rest of Styles --- */
  .stButton > button {{
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    background: {colors['ACCENT']} !important;
    color: #ffffff !important;
    border-radius: 10px !important;
    padding: 10px 22px !important;
    border: none !important;
  }}

  .stChatInput > div {{
    background: {colors['SURFACE']} !important;
    border: 1.5px solid {colors['BORDER']} !important;
    border-radius: 14px !important;
  }}

  .stSuccess {{ background: {colors['GREEN']}22 !important; border-color: {colors['GREEN']} !important; }}
  .stWarning {{ background: {colors['AMBER']}22 !important; border-color: {colors['AMBER']} !important; }}
  .stError {{ background: {colors['RED']}22 !important; border-color: {colors['RED']} !important; }}
</style>
""",
        unsafe_allow_html=True,
    )


def divider():
    colors = get_theme(st.session_state.dark)
    st.markdown(
        f"<hr style='border:none;border-top:1px solid {colors['BORDER']};margin:24px 0;'>",
        unsafe_allow_html=True,
    )


def section_label(text: str):
    colors = get_theme(st.session_state.dark)
    st.markdown(
        f"<p style='font-family:\"DM Mono\",monospace;font-size:0.7rem;"
        f"font-weight:500;letter-spacing:0.14em;text-transform:uppercase;"
        f"color:{colors['TEXT3']};margin-bottom:8px;'>{text}</p>",
        unsafe_allow_html=True,
    )


def _nearest_area_name(lat: float, lon: float) -> str:
    best_name = "Lagos"
    best_distance = float("inf")
    for area_name, coordinates in LAGOS_AREAS.items():
        a_lat, a_lon = coordinates
        distance = ((lat - a_lat) ** 2 + (lon - a_lon) ** 2) ** 0.5
        if distance < best_distance:
            best_distance = distance
            best_name = area_name.title()
    return best_name


def _extract_geolocation(geo_payload):
    if geo_payload is None:
        return None, None, ""

    payload = geo_payload
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return None, None, "Could not parse location payload from browser."

    if not isinstance(payload, dict):
        return None, None, "Unexpected location payload from browser."

    lat = payload.get("latitude")
    lon = payload.get("longitude")
    if lat is not None and lon is not None:
        return float(lat), float(lon), ""

    coords = payload.get("coords") if isinstance(payload.get("coords"), dict) else {}
    lat = coords.get("latitude")
    lon = coords.get("longitude")
    if lat is not None and lon is not None:
        return float(lat), float(lon), ""

    error_text = payload.get("error") or payload.get("message") or ""
    if isinstance(error_text, dict):
        error_text = error_text.get("message", "")
    return None, None, str(error_text)


def auto_fetch_location():
    """
    Renders a button to fetch device location via browser geolocation API.
    Returns lat, lon, location_name if successful, otherwise returns None, None, None.
    """
    colors = get_theme(st.session_state.dark)
    
    st.markdown(
        f"""
    <p style='font-size:0.9rem;color:{colors["TEXT2"]};margin-bottom:12px;'>
    Auto detect uses your device location (GPS/browser geolocation).
    </p>
    """,
        unsafe_allow_html=True,
    )

    if get_geolocation is None:
        st.warning("Device geolocation dependency missing. Install streamlit-js-eval.")
    else:
        if st.button("Automatically Fetch Location", use_container_width=True, key="device_geo_btn"):
            st.session_state.geolocation_device_requested = True
            st.session_state.geolocation_error = ""

        if st.session_state.geolocation_device_requested:
            st.caption("Allow location permission in your browser prompt.")
            payload = get_geolocation(component_key="device_geo")
            lat_val, lon_val, error_text = _extract_geolocation(payload)
            if lat_val is not None and lon_val is not None:
                st.session_state.geolocation_lat = lat_val
                st.session_state.geolocation_lon = lon_val
                st.session_state.geolocation_device_requested = False
                st.session_state.geolocation_error = ""
                st.rerun()
            elif error_text:
                st.session_state.geolocation_error = error_text

        if st.session_state.geolocation_error:
            st.warning(
                f"Device location unavailable: {st.session_state.geolocation_error}. You can enter an area name manually below."
            )

    st.markdown(
        f"<p style='font-size:0.85rem;color:{colors['TEXT3']};margin-top:8px;'>Or enter a Lagos area name below.</p>",
        unsafe_allow_html=True,
    )
    geo_area = st.text_input(
        "Lagos area",
        placeholder="Ikeja, Lekki, VI, Surulere, Yaba...",
        key="geo_area_input",
    )

    if geo_area:
        area_key = geo_area.lower().strip()
        match = LAGOS_AREAS.get(area_key)
        if not match:
            for area_name, coordinates in LAGOS_AREAS.items():
                if area_key in area_name or area_name in area_key:
                    match = coordinates
                    break

        if match:
            st.session_state.geolocation_lat = float(match[0])
            st.session_state.geolocation_lon = float(match[1])
            st.session_state.geolocation_error = ""
        elif len(area_key) >= 3:
            st.warning("Area not found. Try: Ikeja, Lekki, VI, Surulere, Yaba, Ikorodu, Apapa.")
    
    if (
        st.session_state.geolocation_lat is not None
        and st.session_state.geolocation_lon is not None
    ):
        lat = st.session_state.geolocation_lat
        lon = st.session_state.geolocation_lon
        nearest_area = _nearest_area_name(lat, lon)
        location_name = f"{nearest_area} ({lat:.3f}°N, {lon:.3f}°E)"
        
        # Show prominent confirmation message
        colors_local = get_theme(st.session_state.dark)
        st.markdown(
            f"<div style='background:{colors_local['SURFACE2']};border:2px solid {colors_local['ACCENT']};border-radius:10px;padding:12px 16px;margin-top:12px;'>"
            f"<span style='color:{colors_local['ACCENT']};font-weight:700;font-size:0.95rem;'>Found</span> "
            f"<span style='color:{colors_local['TEXT']};font-weight:600;'>{location_name}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        return lat, lon, location_name
    
    return None, None, None


def render_header(logo_path):
    colors = get_theme(st.session_state.dark)
    top_left, top_right = st.columns([9, 1])
    with top_left:
        logo_col, title_col = st.columns([1, 11])
        with logo_col:
            if logo_path.exists():
                st.image(str(logo_path), width=52)
            else:
                st.markdown("<div style='font-size:2rem;'>...</div>", unsafe_allow_html=True)
        with title_col:
            st.markdown(
                f"""
        <div style="padding-top:4px;">
          <span style="font-size:1.7rem;font-weight:800;
                       color:{colors['H_COLOR']};letter-spacing:-0.03em;">FloodIQ</span><br>
          <span style="font-family:'DM Mono',monospace;font-size:0.72rem;
                       color:{colors['ACCENT']};letter-spacing:0.1em;
                       text-transform:uppercase;">Lagos Flood Risk Prediction</span>
        </div>
        """,
                unsafe_allow_html=True,
            )
    with top_right:
        icon = "☀️" if st.session_state.dark else "🌙"
        if st.button(icon, key="theme_btn", help="Toggle theme"):
            st.session_state.dark = not st.session_state.dark
            st.rerun()


def risk_banner(flood_days: int, total: int = 3):
    colors = get_theme(st.session_state.dark)
    if flood_days >= 2:
        bg, border, color, icon, message = (
            f"{colors['RED']}15",
            colors["RED"],
            colors["RED"],
            "⚠",
            f"SEVERE FLOOD RISK - {flood_days}/{total} days at high risk",
        )
    elif flood_days == 1:
        bg, border, color, icon, message = (
            f"{colors['AMBER']}15",
            colors["AMBER"],
            colors["AMBER"],
            "⚠",
            f"FLOOD RISK DETECTED - {flood_days}/{total} day at risk",
        )
    else:
        bg, border, color, icon, message = (
            f"{colors['ACCENT']}15",
            colors["ACCENT"],
            colors["ACCENT"],
            "✓",
            f"ALL CLEAR - No flood risk in the next {total} days",
        )

    st.markdown(
        f"""
    <div style="background:{bg};border:1.5px solid {border};
                border-left:5px solid {border};border-radius:12px;
                padding:16px 20px;display:flex;align-items:center;
                gap:14px;margin:16px 0;">
      <span style="font-size:1.6rem;">{icon}</span>
      <span style="font-weight:700;font-size:1rem;color:{color};">{message}</span>
    </div>
    """,
        unsafe_allow_html=True,
    )


def forecast_cards(predictions):
    colors = get_theme(st.session_state.dark)
    columns = st.columns(3)
    for column, (_, row) in zip(columns, predictions.iterrows()):
        probability = row["flood_prob"]
        percent = round(probability * 100)

        if row["flood_predicted"]:
            card_bg, text_main, text_sub, border = (
                colors["CARD_FLOOD"],
                colors["RED"],
                f"{colors['RED']}AA",
                colors["RED"],
            )
        else:
            card_bg, text_main, text_sub, border = (
                colors["SURFACE"],
                colors["TEXT"],
                colors["TEXT2"],
                colors["BORDER"],
            )

        if probability >= 0.7:
            status_label, status_color = "CRITICAL", colors["RED"]
        elif probability >= 0.4:
            status_label, status_color = "WATCH", colors["AMBER"]
        elif row["tp"] > 5:
            status_label, status_color = "ADVISORY", colors["ACCENT2"]
        else:
            status_label, status_color = "NORMAL", colors["GREEN"]

        bar_color = colors["RED"] if probability >= 0.7 else (colors["AMBER"] if probability >= 0.4 else colors["ACCENT"])

        with column:
            st.markdown(
                f"""
            <div style="background:{card_bg};border:1.5px solid {border};
                        border-radius:14px;padding:18px;
                        box-shadow:0 2px 12px {border}33;">

              <div style="display:flex;justify-content:space-between;
                          align-items:flex-start;margin-bottom:12px;">
                <span style="font-family:'DM Mono',monospace;font-size:0.7rem;
                             color:{text_sub};letter-spacing:0.06em;
                             text-transform:uppercase;">{row['date']}</span>
                <span style="font-size:0.68rem;font-weight:700;
                             font-family:'DM Mono',monospace;
                             letter-spacing:0.08em;padding:3px 9px;
                             border-radius:999px;border:1.5px solid {status_color};
                             color:{status_color};background:{status_color}22;">{status_label}</span>
              </div>

              <div style="margin-bottom:14px;">
                <div style="font-size:1rem;font-weight:800;color:{text_main};">
                  {'Take Flood Precautions' if probability > 0.5 else 'Clear Drains' if probability > 0.2 else 'All Clear'}
                </div>
                <div style="font-size:0.8rem;color:{text_sub};
                            margin-top:4px;font-style:italic;">
                  {'Flood risk is high' if probability > 0.5 else 'Surface runoff likely' if probability > 0.2 else 'No immediate concerns'}
                </div>
              </div>

              <div style="margin:10px 0 6px 0;">
                <div style="display:flex;justify-content:space-between;
                            font-family:'DM Mono',monospace;
                            font-size:0.72rem;color:{text_sub};margin-bottom:4px;">
                  <span>Flood probability</span><span style="color:{text_main};">{percent}%</span>
                </div>
                <div style="height:5px;background:{border};border-radius:999px;overflow:hidden;">
                  <div style="height:100%;width:{percent}%;background:{bar_color};
                              border-radius:999px;"></div>
                </div>
              </div>

              <div style="display:flex;justify-content:space-between;
                          padding-top:10px;border-top:1px solid {border};
                          font-family:'DM Mono',monospace;font-size:0.72rem;
                          color:{text_sub};">
                <span>🌧 {row['tp']:.1f}mm</span>
                <span>🌡 {row['t2m']:.0f}°C</span>
                <span>☁ {row['tcc']:.0f}%</span>
              </div>
            </div>
            """,
                unsafe_allow_html=True,
            )


def chat_bubble(role: str, content: str):
    colors = get_theme(st.session_state.dark)
    if role in ("model", "assistant"):
        bg, text_color, align, radius = (
            colors["SURFACE2"],
            colors["TEXT"],
            "flex-start",
            "14px 14px 14px 4px",
        )
        prefix = ""
    else:
        bg, text_color, align, radius = (
            colors["ACCENT"],
            "#ffffff",
            "flex-end",
            "14px 14px 4px 14px",
        )
        prefix = ""

    st.markdown(
        f"""
    <div style="display:flex;justify-content:{align};margin:8px 0;">
      <div style="background:{bg};color:{text_color};border-radius:{radius};
                  padding:12px 16px;max-width:82%;font-size:0.92rem;
                  line-height:1.6;border:1px solid {colors['BORDER']};">
        {prefix}{content}
      </div>
    </div>
    """,
        unsafe_allow_html=True,
    )