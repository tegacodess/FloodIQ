from __future__ import annotations

from datetime import datetime, date, timedelta

import numpy as np
import pandas as pd
import requests

from .config import (
    ARCHIVE_API_URL,
    FORECAST_API_URL,
    FORECAST_DAYS,
)
import streamlit as st


def _normalize_start_date(start_date):
    if start_date is None:
        return date.today()
    if isinstance(start_date, date):
        return start_date
    return pd.to_datetime(start_date).date()


def _replace_year_safe(target_date: date, year: int):
    try:
        return target_date.replace(year=year)
    except ValueError:
        return None


def _build_open_meteo_frame(data: dict):
    daily = data["daily"]
    hourly = data["hourly"]

    hourly_frame = pd.DataFrame({
        "time": pd.to_datetime(hourly["time"]),
        "soil_moisture": hourly["soil_moisture_0_to_7cm"],
        "runoff_hr": hourly["runoff"],
    })
    hourly_frame["date"] = hourly_frame["time"].dt.date
    aggregated = hourly_frame.groupby("date").agg(
        swvl1=("soil_moisture", "mean"),
        runoff_mm=("runoff_hr", "sum"),
    ).reset_index()

    aggregated = hourly_frame.groupby("date").agg(
    swvl1=("soil_moisture", "mean"),
    runoff_mm=("runoff_hr", "sum"),
    ).reset_index()

    # fill any missing soil moisture with Lagos wet season climatological mean
    aggregated["swvl1"] = aggregated["swvl1"].fillna(0.25)
    aggregated["runoff_mm"] = aggregated["runoff_mm"].fillna(0.0)

    

    records = []
    for index, date_string in enumerate(daily["time"]):
        date_value = pd.to_datetime(date_string).date()
        day_rows = aggregated[aggregated["date"] == date_value]
        swvl1 = float(day_rows["swvl1"].values[0]) if len(day_rows) else 0.2
        runoff_mm = float(day_rows["runoff_mm"].values[0]) if len(day_rows) else 0.0

        records.append({
            "date": date_string,
            "tp_mm": daily["precipitation_sum"][index] or 0.0,
            "temp_c": daily["temperature_2m_mean"][index] or 25.0,
            "swvl1": swvl1,
            "runoff_mm": runoff_mm,
        })

    return pd.DataFrame(records)


def _fetch_open_meteo_window(api_url: str, lat: float, lon: float, days: int, start_date=None):
    start_day = _normalize_start_date(start_date)
    end_day = start_day + timedelta(days=days - 1)

    is_archive = "archive" in api_url

    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": [
            "precipitation_sum",
            "temperature_2m_mean",
        ],
        "hourly": [
            "soil_moisture_0_to_7cm",
            "runoff",
        ],
        "timezone": "Africa/Lagos",
        "start_date": start_day.strftime("%Y-%m-%d"),
        "end_date": end_day.strftime("%Y-%m-%d"),
    }

    # ERA5-Land provides soil moisture and runoff, for forecast endpoint, use the best available model that includes these variables
    if not is_archive:
        params["models"] = "era5_seamless"

    response = requests.get(api_url, params=params, timeout=12)
    response.raise_for_status()
    return _build_open_meteo_frame(response.json())

def _fetch_archive_climatology(lat: float, lon: float, days: int, start_date=None, years: int = 5):
    start_day = _normalize_start_date(start_date)
    buckets = {offset: [] for offset in range(days)}

    for year_offset in range(1, years + 1):
        sample_start = _replace_year_safe(start_day, start_day.year - year_offset)
        if sample_start is None:
            continue
        try:
            sample_frame = _fetch_open_meteo_window(ARCHIVE_API_URL, lat, lon, days, start_date=sample_start)
        except Exception:
            continue

        for offset, (_, row) in enumerate(sample_frame.head(days).iterrows()):
            buckets[offset].append(row)

    records = []
    for offset in range(days):
        samples = buckets[offset]
        if not samples:
            continue

        sample_frame = pd.DataFrame(samples)
        target_date = start_day + timedelta(days=offset)
        records.append({
            "date": target_date.strftime("%Y-%m-%d"),
            "tp_mm": float(sample_frame["tp_mm"].mean()),
            "temp_c": float(sample_frame["temp_c"].mean()),
            "swvl1": float(sample_frame["swvl1"].mean()),
            "runoff_mm": float(sample_frame["runoff_mm"].mean()),
        })

    if not records:
        raise ValueError("Climatology fallback did not produce daily forecast rows")

    return pd.DataFrame(records)


def fetch_weather(lat, lon, days=FORECAST_DAYS, start_date=None):
    start_day = _normalize_start_date(start_date)
    today = date.today()
    forecast_horizon = today + timedelta(days=16)

    try:
        if start_day < today:
            return _fetch_open_meteo_window(ARCHIVE_API_URL, lat, lon, days, start_date=start_day), None, "archive"
        if start_day <= forecast_horizon:
            return _fetch_open_meteo_window(FORECAST_API_URL, lat, lon, days, start_date=start_day), None, "forecast"
        return _fetch_archive_climatology(lat, lon, days, start_day), None, "climatology"

    except Exception as primary_error:
        # Fallback: try climatology from archive regardless of date
        try:
            return _fetch_archive_climatology(lat, lon, days, start_day), None, "climatology"
        except Exception as fallback_error:
            return None, f"Weather fetch failed: {primary_error}; climatology fallback failed: {fallback_error}", None


def build_context(
    predictions: pd.DataFrame,
    location_name: str,
    lat: float,
    lon: float,
    grid_cell,
    weather_mode: str = "forecast",
):
    mode_descriptions = {
        "archive": "Historical analysis from archived weather data (selected date is in the past)",
        "forecast": "Forward-looking forecast from Open-Meteo",
        "climatology": "Climatology estimate built from historical archive samples",
    }
    mode_label = mode_descriptions.get(weather_mode, "Unknown weather data source")
    window_start = str(predictions["date"].min()) if not predictions.empty else "N/A"
    window_end = str(predictions["date"].max()) if not predictions.empty else "N/A"

    lines = [
        f"Location: {location_name} (Lat {lat:.4f}, Lon {lon:.4f})",
        f"Nearest ERA5 grid cell: {grid_cell}",
        f"Analysis generated on: {datetime.now().strftime('%Y-%m-%d')}",
        f"Weather source mode: {mode_label}",
        f"3-day analysis window: {window_start} to {window_end}",
        "",
        "3-Day Flood Risk Output:",
    ]
    for _, row in predictions.iterrows():
        lines.append(
            f"  • {row['date']}: {row['risk_level']} RISK (probability {row['flood_prob']*100:.1f}%, rainfall {row['tp_mm']:.1f}mm)"
        )
    return "\n".join(lines)


def groq_chat(api_key: str, history: list, context: str):
    system = f"""You are FloodIQ, a flood risk assistant for Lagos State, Nigeria.
Help users understand flood predictions and give practical safety advice.

CURRENT PREDICTION CONTEXT:
{context}

Guidelines:
- Be concise, clear and practical
- Give actionable advice specific to Lagos
- Reference the prediction data when relevant
- If weather source mode says archived/historical, explicitly say this is a retrospective analysis, not a future forecast
- If weather source mode says climatology, explicitly say this is an estimate based on historical patterns
- Prioritise safety
- Keep responses under 200 words"""

    messages = [{"role": "system", "content": system}]
    for message in history:
        role = "assistant" if message["role"] in ("model", "assistant") else "user"
        messages.append({"role": role, "content": message["content"]})

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
                "max_tokens": 400,
                "temperature": 0.7,
            },
            timeout=12,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"], None
    except requests.exceptions.HTTPError as error:
        return None, f"Groq error {error.response.status_code}: {error.response.text}"
    except Exception as error:
        return None, str(error)
