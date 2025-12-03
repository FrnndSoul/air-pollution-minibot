from resources.email import send_spike_alert_if_enabled

# Dummy spiking sensors
spiking_sensors = ["aqi", "pm25", "voc"]

# Fake readings
metrics = {
    "aqi": 180,
    "pm25": 55,
    "pm10": 80,
    "voc": 420,
    "temp": 30,
    "humidity": 60,
    "toxic": 0.5,
    "flammable": 0.4,
    "smoke": 0.6,
}

# Fake AQI trend
aqi_trend = {
    "slope": 2.1,
    "current_aqi": 180,
    "predicted_peak": 210,
}

sent = send_spike_alert_if_enabled(
    spiking_sensors=spiking_sensors,
    metrics=metrics,
    aqi_trend=aqi_trend,
    forecast_window_minutes=30,
)

print("Email sent?", sent)
