from functools import lru_cache
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import json

import joblib
import pandas as pd
from sklearn.preprocessing import LabelEncoder


ROOT = Path(__file__).resolve().parents[1]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
AREA_COORDINATES = {
    "Other": (9.00, 38.70),
    "Office areas": (9.02, 38.75),
    "Residential areas": (8.98, 38.68),
    "Church areas": (9.05, 38.72),
    "Industrial areas": (8.95, 38.65),
    "School areas": (9.01, 38.80),
    "Recreational areas": (9.08, 38.78),
    "Outside Addis Ababa": (8.50, 38.20),
    "Hospital areas": (9.03, 38.71),
    "Market areas": (9.00, 38.74),
    "Rural village areas": (8.70, 38.50),
    "Unknown": (9.00, 38.70),
}
CATEGORICAL_INPUTS = {
    "Day_of_week": "day_of_week",
    "Weather_conditions": "weather",
    "Road_surface_type": "road_surface",
    "Light_conditions": "light_conditions",
    "Cause_of_accident": "cause",
    "Types_of_Junction": "junction_type",
}
CLASS_NAMES = {0: "Fatal injury", 1: "Serious Injury", 2: "Slight Injury"}


@lru_cache(maxsize=1)
def load_assets():
    data = pd.read_csv(ROOT / "data" / "Road.csv")
    model = joblib.load(ROOT / "models" / "accident_model.pkl")
    feature_columns = joblib.load(ROOT / "models" / "feature_columns.pkl")
    encoders = {
        column: LabelEncoder().fit(data[column].astype(str))
        for column in CATEGORICAL_INPUTS
    }
    return data, model, feature_columns, encoders


def category_options(data, column):
    return sorted(data[column].dropna().astype(str).unique().tolist())


def dashboard_payload(query):
    data, _, _, _ = load_assets()
    filtered = data
    filters = {
        "Weather_conditions": query.get("weather", "All"),
        "Day_of_week": query.get("day", "All"),
        "Accident_severity": query.get("severity", "All"),
    }
    for column, value in filters.items():
        if value != "All":
            if value not in category_options(data, column):
                raise ValueError(f"Invalid {column} filter")
            filtered = filtered[filtered[column].astype(str) == value]

    severity_counts = filtered["Accident_severity"].value_counts()
    day_counts = filtered["Day_of_week"].value_counts()
    weather_table = pd.crosstab(filtered["Weather_conditions"], filtered["Accident_severity"])
    weather_rows = []
    for weather, row in weather_table.iterrows():
        weather_rows.append({
            "weather": str(weather),
            "Fatal injury": int(row.get("Fatal injury", 0)),
            "Serious Injury": int(row.get("Serious Injury", 0)),
            "Slight Injury": int(row.get("Slight Injury", 0)),
        })
    weather_rows.sort(key=lambda row: sum(row[name] for name in CLASS_NAMES.values()), reverse=True)

    hotspot_counts = filtered["Area_accident_occured"].dropna().value_counts()
    hotspots = []
    for area, count in hotspot_counts.items():
        latitude, longitude = AREA_COORDINATES.get(str(area), (9.0, 38.7))
        hotspots.append({
            "area": str(area),
            "count": int(count),
            "latitude": latitude,
            "longitude": longitude,
        })

    severity_totals = {
        "fatal": int(sum(count for name, count in severity_counts.items() if "fatal" in str(name).lower())),
        "serious": int(sum(count for name, count in severity_counts.items() if "serious" in str(name).lower())),
        "slight": int(sum(count for name, count in severity_counts.items() if "slight" in str(name).lower())),
    }
    return {
        "total": int(len(filtered)),
        **severity_totals,
        "by_severity": {str(name): int(count) for name, count in severity_counts.items()},
        "by_day": [{"day": day, "count": int(day_counts.get(day, 0))} for day in WEEKDAYS],
        "weather_severity": weather_rows[:8],
        "top_causes": [
            {"cause": str(cause), "count": int(count)}
            for cause, count in filtered["Cause_of_accident"].dropna().value_counts().head(10).items()
        ],
        "hotspots": hotspots,
        "options": {
            "weather": category_options(data, "Weather_conditions"),
            "day": WEEKDAYS,
            "severity": category_options(data, "Accident_severity"),
            "road_surface": category_options(data, "Road_surface_type"),
            "light_conditions": category_options(data, "Light_conditions"),
            "cause": category_options(data, "Cause_of_accident"),
            "junction_type": category_options(data, "Types_of_Junction"),
        },
    }


def predict(payload):
    if not isinstance(payload, dict):
        raise ValueError("Prediction input must be a JSON object")

    data, model, feature_columns, encoders = load_assets()
    numeric_inputs = {
        "Hour": ("hour", 0, 23),
        "Number_of_vehicles_involved": ("num_vehicles", 1, 10),
        "Number_of_casualties": ("num_casualties", 1, 10),
    }
    values = {column: 0 for column in feature_columns}
    for column, (key, minimum, maximum) in numeric_inputs.items():
        try:
            number = int(payload[key])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"{key} must be an integer") from None
        if not minimum <= number <= maximum:
            raise ValueError(f"{key} must be between {minimum} and {maximum}")
        values[column] = number

    for column, key in CATEGORICAL_INPUTS.items():
        value = payload.get(key)
        if value not in category_options(data, column):
            raise ValueError(f"Invalid {key} option")
        values[column] = int(encoders[column].transform([value])[0])

    input_row = pd.DataFrame([[values[column] for column in feature_columns]], columns=feature_columns)
    prediction = int(model.predict(input_row)[0])
    probabilities = model.predict_proba(input_row)[0]
    probability_rows = [
        {"name": CLASS_NAMES.get(int(label), str(label)), "value": round(float(probability) * 100, 1)}
        for label, probability in zip(model.classes_, probabilities)
    ]
    probability_rows.sort(key=lambda item: item["value"], reverse=True)
    return {
        "class": prediction,
        "severity": CLASS_NAMES.get(prediction, str(prediction)),
        "confidence": round(max(float(value) for value in probabilities) * 100, 1),
        "probabilities": probability_rows,
    }


class handler(BaseHTTPRequestHandler):
    def _send_json(self, status, payload):
        body = json.dumps(payload, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        request = urlparse(self.path)
        if request.path != "/api":
            self._send_json(404, {"error": "Not found"})
            return
        query = {key: values[0] for key, values in parse_qs(request.query).items()}
        if query.get("action") != "dashboard":
            self._send_json(400, {"error": "Unsupported action"})
            return
        try:
            self._send_json(200, dashboard_payload(query))
        except ValueError as error:
            self._send_json(400, {"error": str(error)})
        except Exception:
            self.log_exception("Dashboard request failed")
            self._send_json(500, {"error": "Dashboard data could not be loaded"})

    def do_POST(self):
        request = urlparse(self.path)
        query = parse_qs(request.query)
        if request.path != "/api" or query.get("action") != ["predict"]:
            self._send_json(404, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 16384:
                self._send_json(413, {"error": "Request is too large"})
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            self._send_json(200, predict(payload))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            self._send_json(400, {"error": str(error) or "Invalid JSON request"})
        except Exception:
            self.log_exception("Prediction request failed")
            self._send_json(500, {"error": "Prediction could not be generated"})

    def log_message(self, format, *args):
        return