class Predictor:
    def __init__(self, db_path):
        self.db_path = db_path

    def load_sensor_history(self, sensor_name, limit=200):
        import pandas as pd
        df = pd.read_csv(self.db_path)
        df = df[df["sensor"] == sensor_name].tail(limit)
        return df["value"].astype(float)

    def predict_next_5min(self, sensor_name):
        import warnings
        from statsmodels.tsa.arima.model import ARIMA
        warnings.filterwarnings("ignore")

        values = self.load_sensor_history(sensor_name)

        if len(values) < 10:
            return None

        model = ARIMA(values, order=(3,1,2))
        model_fit = model.fit()

        forecast = model_fit.forecast(steps=1)
        return float(forecast[0])
