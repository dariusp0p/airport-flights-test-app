
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
from sklearn.ensemble import RandomForestClassifier


# CONFIGURATION
class Config:
    #??
    WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY", "")
    WEATHER_API_URL = os.environ.get(
        "WEATHER_API_URL",
        "https://api.openweathermap.org/data/2.5/weather",
    )
    CSV_FILE = os.environ.get("FLIGHTS_CSV", "flights.csv")

# DATA FETCHING LAYER

def get_oradea_weather() -> Dict[str, Any]:
    #Call the configured weather API and return a small feature set.
    
    params = {
        "q": "Oradea,RO",
        "appid": Config.WEATHER_API_KEY,
        "units": "metric",
    }
    try:
        resp = requests.get(Config.WEATHER_API_URL, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return {
            "temp": data["main"]["temp"],
            "wind_speed": data["wind"]["speed"],
            "visibility": data.get("visibility", 10000),
        }
    except Exception:  # pragma: no cover - network/environment dependent
        # fallback values used for local development or missing config
        return {"temp": 20.0, "wind_speed": 5.0, "visibility": 10000}

def _generate_dummy_csv(path: str) -> pd.DataFrame:
    """Create a small synthetic training set and save it to 'path'.

    The real project should collect historical flight information and weather
    measurements.  This helper is only here so the module is runnable without
    additional data.
    """
    now = datetime.datetime.now()
    records: list[Dict[str, Any]] = []
    for i in range(50):
        records.append(
            {
                "flight_number": f"FL{i:03}",
                "scheduled_time": (now + datetime.timedelta(hours=i)).isoformat(),
                "priority": random.choice([0, 1]),
                # pretend we observed the actual ground delay in minutes
                "actual_delay": random.randint(0, 120),
            }
        )
    df = pd.DataFrame(records)
    df.to_csv(path, index=False)
    return df

def load_flights_data() -> pd.DataFrame:
    """Load a dataset containing historical flight records from CSV.

    The file is expected to contain at least the columns ``scheduled_time``
    (ISO formatted string), ``priority`` and ``actual_delay`` which serves as
    the target variable.  If the configured CSV file does not exist we
    generate a small dummy dataset so that the script can be executed for
    demonstration purposes without extra preparation.
    """
    if not os.path.exists(Config.CSV_FILE):
        print(f"{Config.CSV_FILE} not found; generating dummy data")
        return _generate_dummy_csv(Config.CSV_FILE)

    df = pd.read_csv(Config.CSV_FILE, parse_dates=["scheduled_time"])
    # ensure required columns are present
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
        # expecting pandas DataFrame with a column named 'scheduled_time'
        df = pd.DataFrame(X)
        dt = pd.to_datetime(df["scheduled_time"])
        return pd.DataFrame(
            {
                "hour": dt.dt.hour,
                "day_of_week": dt.dt.dayofweek,
            }
        )


def make_pipeline() -> Pipeline:
    """Construct a preprocessing + classifier pipeline.

    The pipeline performs basic feature engineering on the raw flight
    dataframe (extracting datetime parts, encoding categorical values,
    scaling numeric columns), then trains a `RandomForestClassifier` to
    predict whether a flight will be delayed (i.e. ``actual_delay > 0``).
    """

    # numeric features coming from weather or flight priority/hours
    numeric_features = ["temp", "wind_speed", "visibility", "priority", "hour", "day_of_week"]
    numeric_transformer = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    # if you have any categorical columns (e.g. airline), add them here
    categorical_features = []
    categorical_transformer = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="constant", fill_value="unknown")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )

    preprocessor = ColumnTransformer(
        [
            ("num", numeric_transformer, numeric_features),
            ("cat", categorical_transformer, categorical_features),
        ],
        remainder="drop",
    )

    clf = RandomForestClassifier(n_estimators=100, random_state=42)

    return Pipeline([("datetime_ext", DateTimeFeatureExtractor()), ("preproc", preprocessor), ("clf", clf)])


class FlightDelayModel:
    """Wrapper around an sklearn pipeline for clarity."""

    def __init__(self):
        self.pipeline: Pipeline | None = None

    def train(self, df: pd.DataFrame) -> None:
        """Train the pipeline using a raw flight dataframe.

        The dataframe must include the following columns:

        * scheduled_time(datetime or parseable string)
        * priority(numeric)
        * actual_delay(numeric target)
        * weather features (``temp``, ``wind_speed``, ``visibility``)

        The method will create a binary label ``delayed`` where
        ``actual_delay > 0`` and fit the entire preprocessing pipeline plus
        classifier.
        """
        # compute target
        df = df.copy()
        df["delayed"] = (df["actual_delay"] > 0).astype(int)

        # if weather features are not part of df, attach current snapshot
        if "temp" not in df.columns:
            weather = get_oradea_weather()
            for k, v in weather.items():
                df[k] = v

        X = df[["scheduled_time", "priority", "temp", "wind_speed", "visibility"]]
        y = df["delayed"]

        self.pipeline = make_pipeline()
        self.pipeline.fit(X, y)

    def predict(self, X: pd.DataFrame) -> pd.Series:
        """Return binary delay predictions for a dataframe of flights.

        The input needs the same columns consumed by ``train`` (excluding
        ``actual_delay``).  The returned series contains 0/1 values.
        """
        if self.pipeline is None:
            raise RuntimeError("model has not been trained")
        return pd.Series(self.pipeline.predict(X))


# BUSINESS LOGIC LAYER
def process_flights(flights_df: pd.DataFrame, model: FlightDelayModel) -> pd.DataFrame:
    """Add predicted delay flags to incoming flights.

    The dataframe should contain the training features (scheduled_time,
    priority, and optionally weather).  Missing weather triggers a one‑time
    fetch from the API.
    """
    df = flights_df.copy()
    if "temp" not in df.columns:
        weather = get_oradea_weather()
        for k, v in weather.items():
            df[k] = v

    feature_cols = ["scheduled_time", "priority", "temp", "wind_speed", "visibility"]
    X = df[feature_cols]
    df["predicted_delay"] = model.predict(X)
    return df

# MAIN ENTRY POINT
if __name__ == "__main__":
    # load training data and fit classifier
    historical = load_flights_data()
    model = FlightDelayModel()
    model.train(historical)

    # example prediction on the historical set; replace with new arrivals
    sample = historical.copy()
    predicted = process_flights(sample, model)
    print(predicted.head())