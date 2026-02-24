# IMPORTS
import os
import json
import random
import datetime
from typing import Dict, Any
import pandas as pd
import requests
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.ensemble import RandomForestRegressor

# CONFIGURATION
class Config:
    # Open-Meteo is free and open-source, no key needed!
    WEATHER_API_URL = os.environ.get(
        "WEATHER_API_URL",
        "https://api.open-meteo.com/v1/forecast?latitude=47.0253&longitude=21.9025&current=temperature_2m,wind_speed_10m,visibility&timezone=auto"
    )
    CSV_FILE = os.environ.get("FLIGHTS_CSV", "flights.csv")

# DATA FETCHING LAYER
def get_oradea_weather() -> Dict[str, Any]:
    """Call the Open-Meteo API and return the current weather features."""
    try:
        resp = requests.get(Config.WEATHER_API_URL, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        
        return {
            "temp": data["current"]["temperature_2m"],
            "wind_speed": data["current"]["wind_speed_10m"],
            "visibility": data["current"]["visibility"],
        }
    except Exception as e:
        print(f"Weather API fetch failed: {e}")
        # Fallback values used if there is no internet connection
        return {"temp": 20.0, "wind_speed": 5.0, "visibility": 10000}

def _generate_dummy_csv(path: str) -> pd.DataFrame:
    """Create a small synthetic training set and save it."""
    now = datetime.datetime.now()
    records: list[Dict[str, Any]] = []
    for i in range(50):
        records.append({
            "flight_number": f"FL{i:03}",
            "scheduled_time": (now + datetime.timedelta(hours=i)).isoformat(),
            "priority": random.choice([0, 1]),
            "temp": random.uniform(-5.0, 35.0),
            "wind_speed": random.uniform(0.0, 50.0),
            "visibility": random.choice([1000, 5000, 10000]), 
            "actual_delay": random.randint(0, 120),
        })
    df = pd.DataFrame(records)
    df.to_csv(path, index=False)
    return df

def load_flights_data() -> pd.DataFrame:
    """Load historical flight records from CSV to train the model."""
    if not os.path.exists(Config.CSV_FILE):
        print(f"{Config.CSV_FILE} not found; generating dummy data")
        return _generate_dummy_csv(Config.CSV_FILE)

    df = pd.read_csv(Config.CSV_FILE, parse_dates=["scheduled_time"])
    required = {"scheduled_time", "priority", "actual_delay"}
    if not required.issubset(df.columns):
        raise ValueError(f"CSV missing required columns: {required - set(df.columns)}")
    return df

# ML MODEL LAYER

class DateTimeFeatureExtractor(BaseEstimator, TransformerMixin):
    """Custom transformer to extract hour/day features from the scheduled_time column."""
    def fit(self, X, y=None):
        return self

    def transform(self, X):
        df = pd.DataFrame(X).copy()
        dt = pd.to_datetime(df["scheduled_time"], utc=True)
        df["hour"] = dt.dt.hour
        df["day_of_week"] = dt.dt.dayofweek
        return df

def make_pipeline() -> Pipeline:
    """Construct a preprocessing + regressor pipeline."""
    numeric_features = ["temp", "wind_speed", "visibility", "priority", "hour", "day_of_week"]
    numeric_transformer = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    categorical_features = []
    categorical_transformer = Pipeline([
        ("imputer", SimpleImputer(strategy="constant", fill_value="unknown")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])

    preprocessor = ColumnTransformer(
        [("num", numeric_transformer, numeric_features),
         ("cat", categorical_transformer, categorical_features)],
        remainder="drop",
    )

    regressor = RandomForestRegressor(n_estimators=100, random_state=42)

    return Pipeline([
        ("datetime_ext", DateTimeFeatureExtractor()), 
        ("preproc", preprocessor), 
        ("regressor", regressor)
    ])

class FlightDelayModel:
    """Wrapper around an sklearn pipeline for clarity."""
    def __init__(self):
        self.pipeline: Pipeline | None = None

    def train(self, df: pd.DataFrame) -> None:
        """Train the pipeline to predict actual delay minutes."""
        df = df.copy()

        # If weather features are not part of df, attach current snapshot
        if "temp" not in df.columns:
            weather = get_oradea_weather()
            for k, v in weather.items():
                df[k] = v

        X = df[["scheduled_time", "priority", "temp", "wind_speed", "visibility"]]
        y = df["actual_delay"] 

        self.pipeline = make_pipeline()
        self.pipeline.fit(X, y)

    def predict(self, X: pd.DataFrame) -> pd.Series:
        """Return delay predictions (in minutes) for a dataframe of flights."""
        if self.pipeline is None:
            raise RuntimeError("model has not been trained")
            
        predictions = self.pipeline.predict(X)
        return pd.Series(predictions).round().astype(int)

# BUSINESS LOGIC LAYER (API Handlers)

def process_frontend_payload(json_data: dict, trained_model: FlightDelayModel) -> list:
    """
    Takes a JSON dictionary from the frontend, predicts delays, 
    and returns the updated flight schedule.  The output format is
    intentionally compatible with the existing frontend: each
    record contains an `estimatedDelay` field (minutes) as well as
    the original flight information.
    """
    df_incoming = pd.DataFrame(json_data["flights"])

    # Map JSON keys to what the ML Model expects
    df_incoming["scheduled_time"] = df_incoming["scheduledArrival"]
    df_incoming["priority"] = 1  # Add default priority

    # Fetch real-time weather and attach it to the flights
    weather = get_oradea_weather()
    for k, v in weather.items():
        df_incoming[k] = v

    # Predict the delays
    feature_cols = ["scheduled_time", "priority", "temp", "wind_speed", "visibility"]
    X_incoming = df_incoming[feature_cols]
    df_incoming["predicted_delay_mins"] = trained_model.predict(X_incoming)

    # Calculate the NEW Arrival Time
    def calculate_new_arrival(row):
        dt = pd.to_datetime(row["scheduledArrival"])
        new_dt = dt + datetime.timedelta(minutes=row["predicted_delay_mins"])
        return new_dt.isoformat()

    df_incoming["new_arrival_time"] = df_incoming.apply(calculate_new_arrival, axis=1)

    # Format the output to send back to frontend
    # keep most of the original flight information so the frontend table
    # can display fields such as `from` and `to`.
    output_columns = [
        "flightNumber",
        "airline",
        "from",
        "to",
        "scheduledArrival",
        "predicted_delay_mins",
        "new_arrival_time",
    ]

    results = df_incoming[output_columns].to_dict(orient="records")
    # rename the prediction field to match what the React app currently
    # expects (`estimatedDelay`), but also keep the raw value if someone
    # wants the more explicit name later.
    for r in results:
        r["estimatedDelay"] = r.pop("predicted_delay_mins")
    return results


# MAIN ENTRY POINT (Test Simulation)

if __name__ == "__main__":
    # 1. Train the model ONCE when the app starts
    historical = load_flights_data()
    model = FlightDelayModel()
    model.train(historical)
    print("Model trained successfully!\n")

    # 2. Simulate the frontend sending a JSON payload directly via an API call
    incoming_frontend_request = {
      "flights": [
        {
          "flightNumber": "W63012",
          "airline": "Wizz Air",
          "from": "OTP",
          "to": "LTN",
          "scheduledArrival": "2026-02-20T07:30:00+00:00"
        },
        {
          "flightNumber": "RO301",
          "airline": "TAROM",
          "from": "OTP",
          "to": "CDG",
          "scheduledArrival": "2026-02-20T12:20:00+01:00"
        }
      ]
    }
    
    print("Processing incoming frontend JSON request...\n")
    
    # 3. Process it!
    results = process_frontend_payload(incoming_frontend_request, model)
    
    print("Final Output Payload (Send this back to Frontend):")
    print(json.dumps(results, indent=2))