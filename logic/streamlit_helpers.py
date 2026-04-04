from __future__ import annotations

from datetime import datetime, date, timedelta

import numpy as np
import pandas as pd
import requests

from .config import (
    ARCHIVE_API_URL,
    FALLBACK_FORECAST_API_URL,
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

    hourly_frame = pd.DataFrame(
        {
            "time": pd.to_datetime(hourly["time"]),
            "d2m_k": hourly["dewpoint_2m"],
            "msl": hourly["surface_pressure"],
            "precip_hr": hourly["precipitation"],
        }
    )
    hourly_frame["date"] = hourly_frame["time"].dt.date
    aggregated = hourly_frame.groupby("date").agg(
        d2m_k=("d2m_k", "mean"),
        msl=("msl", "mean"),
        mxtpr=("precip_hr", "max"),
    ).reset_index()

    records = []
    for index, date_string in enumerate(daily["time"]):
        date_value = pd.to_datetime(date_string).date()
        day_rows = aggregated[aggregated["date"] == date_value]
        d2m = float(day_rows["d2m_k"].values[0]) if len(day_rows) else 24.0
        msl = float(day_rows["msl"].values[0]) if len(day_rows) else 1013.25
        mxtpr = float(day_rows["mxtpr"].values[0]) if len(day_rows) else 0.0

        wind_speed = daily["windspeed_10m_max"][index] or 0.0
        wind_direction = daily["winddirection_10m_dominant"][index] or 0.0
        wind_direction_rad = np.radians(wind_direction)

        records.append(
            {
                "date": date_string,
                "tp": daily["precipitation_sum"][index] or 0.0,
                "u10": -wind_speed * np.sin(wind_direction_rad),
                "v10": -wind_speed * np.cos(wind_direction_rad),
                "d2m": d2m,
                "t2m": daily["temperature_2m_mean"][index] or 25.0,
                "msl": msl,
                "tcc": daily["cloudcover_mean"][index] or 0.0,
                "mxtpr": mxtpr,
            }
        )

    return pd.DataFrame(records)


def _fetch_open_meteo_window(api_url: str, lat: float, lon: float, days: int, start_date=None):
    start_day = _normalize_start_date(start_date)
    end_day = start_day + timedelta(days=days - 1)

    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": [
            "precipitation_sum",
            "windspeed_10m_max",
            "winddirection_10m_dominant",
            "dewpoint_2m_mean",
            "temperature_2m_mean",
            "surface_pressure_mean",
            "cloudcover_mean",
            "precipitation_hours",
        ],
        "hourly": ["dewpoint_2m", "surface_pressure", "precipitation"],
        "timezone": "Africa/Lagos",
        "start_date": start_day.strftime("%Y-%m-%d"),
        "end_date": end_day.strftime("%Y-%m-%d"),
        "wind_speed_unit": "ms",
    }

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
        records.append(
            {
                "date": target_date.strftime("%Y-%m-%d"),
                "tp": float(sample_frame["tp"].mean()),
                "u10": float(sample_frame["u10"].mean()),
                "v10": float(sample_frame["v10"].mean()),
                "d2m": float(sample_frame["d2m"].mean()),
                "t2m": float(sample_frame["t2m"].mean()),
                "msl": float(sample_frame["msl"].mean()),
                "tcc": float(sample_frame["tcc"].mean()),
                "mxtpr": float(sample_frame["mxtpr"].mean()),
            }
        )

    if not records:
        raise ValueError("Climatology fallback did not produce daily forecast rows")

    return pd.DataFrame(records)


def _fetch_met_no(lat: float, lon: float, days: int, start_date=None):
    start_day = _normalize_start_date(start_date)

    headers = {
        "User-Agent": "FloodIQ/1.0 (contact: tegazion7@gmail.com)",
    }
    response = requests.get(
        FALLBACK_FORECAST_API_URL,
        params={"lat": lat, "lon": lon},
        headers=headers,
        timeout=12,
    )
    response.raise_for_status()
    payload = response.json()

    timeseries = payload.get("properties", {}).get("timeseries", [])
    if not timeseries:
        raise ValueError("Fallback API returned no timeseries data")

    rows = []
    for point in timeseries:
        details = point.get("data", {}).get("instant", {}).get("details", {})
        next_1h = point.get("data", {}).get("next_1_hours", {}).get("details", {})
        timestamp = pd.to_datetime(point.get("time"), utc=True).tz_convert("Africa/Lagos")
        rows.append(
            {
                "time": timestamp,
                "tp_hour": float(next_1h.get("precipitation_amount", 0.0) or 0.0),
                "u10": float(details.get("x_wind", 0.0) or 0.0),
                "v10": float(details.get("y_wind", 0.0) or 0.0),
                "d2m": float(details.get("dew_point_temperature", 24.0) or 24.0),
                "t2m": float(details.get("air_temperature", 25.0) or 25.0),
                "msl": float(details.get("air_pressure_at_sea_level", 1013.25) or 1013.25),
                "tcc": float(details.get("cloud_area_fraction", 0.0) or 0.0),
            }
        )

    frame = pd.DataFrame(rows)
    frame["date"] = frame["time"].dt.date
    daily = (
        frame.groupby("date")
        .agg(
            tp=("tp_hour", "sum"),
            u10=("u10", "mean"),
            v10=("v10", "mean"),
            d2m=("d2m", "mean"),
            t2m=("t2m", "mean"),
            msl=("msl", "mean"),
            tcc=("tcc", "mean"),
            mxtpr=("tp_hour", "max"),
        )
        .reset_index()
    )

    daily = daily[daily["date"] >= start_day]
    daily = daily.head(days)
    if daily.empty:
        raise ValueError("Fallback API did not produce daily forecast rows")

    daily["date"] = pd.to_datetime(daily["date"]).dt.strftime("%Y-%m-%d")
    return daily[["date", "tp", "u10", "v10", "d2m", "t2m", "msl", "tcc", "mxtpr"]]


def fetch_weather(lat: float, lon: float, days: int = FORECAST_DAYS, start_date=None):
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
        try:
            fallback_df = _fetch_met_no(lat, lon, days, start_date=start_date)
            return fallback_df, None, "fallback"
        except Exception as fallback_error:
            return None, f"Open-Meteo failed: {primary_error}; fallback failed: {fallback_error}", None


def build_context(predictions: pd.DataFrame, location_name: str, lat: float, lon: float, grid_cell):
    lines = [
        f"Location: {location_name} (Lat {lat:.4f}, Lon {lon:.4f})",
        f"Nearest ERA5 grid cell: {grid_cell}",
        f"Prediction date: {datetime.now().strftime('%Y-%m-%d')}",
        "",
        "3-Day Flood Risk Forecast:",
    ]
    for _, row in predictions.iterrows():
        lines.append(
            f"  • {row['date']}: {row['risk_level']} RISK (probability {row['flood_prob'] * 100:.1f}%, rainfall {row['tp']:.1f}mm)"
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
