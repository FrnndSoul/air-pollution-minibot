# resources/gen_message.py
from typing import Dict, Iterable, List, Optional, Tuple

# Sensor keys match the dashboard_readings table in store.py
SENSOR_LABELS: Dict[str, str] = {
    "aqi": "Air Quality Index",
    "pm25": "PM2.5 (fine particulate matter)",
    "pm10": "PM10 (coarse particulate matter)",
    "temp": "Temperature",
    "humidity": "Humidity",
    "toxic": "Toxic gas index",
    "flammable": "Flammable gas index",
    "smoke": "Smoke index",
    "voc": "VOC index",
}

SENSOR_TIPS: Dict[str, str] = {
    "aqi": (
        "Keep windows closed if outdoor air is polluted and consider using an air purifier "
        "to improve indoor air quality."
    ),
    "pm25": (
        "Fine particles can reach deep into the lungs. Limit vigorous activity, "
        "especially for children, the elderly, and those with respiratory conditions."
    ),
    "pm10": (
        "Coarse particles often come from dust and debris. Consider reducing dust sources "
        "and using filtration if possible."
    ),
    "temp": (
        "If the temperature is uncomfortable, consider adjusting ventilation or cooling "
        "to keep the space within a safe range."
    ),
    "humidity": (
        "Very high humidity can promote mold growth. Very low humidity can irritate "
        "eyes and airways. Aim for about 40 to 60 percent."
    ),
    "toxic": (
        "Elevated toxic gas readings can indicate harmful substances in the air. "
        "Increase ventilation, identify potential sources, and leave the area if you feel unwell."
    ),
    "flammable": (
        "High flammable gas readings can indicate a fire hazard. Check for gas leaks, "
        "avoid open flames, and follow your local safety procedures."
    ),
    "smoke": (
        "Smoke can signal fire or combustion. Check your surroundings and follow your "
        "fire safety plan if needed."
    ),
    "voc": (
        "High VOC levels often come from cleaning products, paints, or solvents. "
        "Increase ventilation and reduce use of strong chemicals where possible."
    ),
}


def _sensor_display_name(sensor_key: str) -> str:
    return SENSOR_LABELS.get(sensor_key, sensor_key)


def _format_value(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


def _format_spike_line(sensor_key: str, metrics: Optional[Dict[str, float]]) -> str:
    label = _sensor_display_name(sensor_key)
    if metrics is None:
        return f"- {label}: spike detected"

    value = metrics.get(sensor_key)
    return f"- {label}: { _format_value(value) } (spike detected)"


def _build_trend_sentence(
    aqi_trend: Optional[Dict[str, float]],
    forecast_window_minutes: Optional[int],
) -> Optional[str]:
    """
    Describe AQI tendency to peak.

    aqi_trend is expected to be a simple dict such as:
      {
        "slope": float,           # positive if trending upward
        "current_aqi": float,
        "predicted_peak": float,  # optional
      }
    but the function is tolerant of missing keys.
    """
    if not aqi_trend:
        return None

    slope = aqi_trend.get("slope")
    current = aqi_trend.get("current_aqi")
    peak = aqi_trend.get("predicted_peak")

    parts: List[str] = []

    if slope is not None:
        if slope > 0:
            parts.append("The Air Quality Index appears to be trending upward.")
        elif slope < 0:
            parts.append("The Air Quality Index appears to be trending downward.")
        else:
            parts.append("The Air Quality Index is relatively stable at the moment.")
    else:
        parts.append("There is an indication that AQI may change soon.")

    if current is not None:
        parts.append(f"Current AQI is approximately {current:.0f}.")

    if peak is not None:
        if forecast_window_minutes:
            parts.append(
                f"It may peak around {peak:.0f} in the next {forecast_window_minutes} minutes."
            )
        else:
            parts.append(f"It may peak around {peak:.0f}.")

    return " ".join(parts)


def _build_safety_tips(spiking_sensors: Iterable[str]) -> List[str]:
    tips: List[str] = []
    for key in spiking_sensors:
        tip = SENSOR_TIPS.get(key)
        if tip and tip not in tips:
            tips.append(tip)
    return tips


def build_alert_message(
    spiking_sensors: Iterable[str],
    metrics: Optional[Dict[str, float]] = None,
    aqi_trend: Optional[Dict[str, float]] = None,
    forecast_window_minutes: Optional[int] = None,
) -> Tuple[str, str, Optional[str]]:
    """
    Build a generative style subject and body for an email alert.

    spiking_sensors:
        Iterable of sensor keys that are currently peaking. Example:
        ["aqi", "pm25", "voc"]

    metrics:
        Optional dict with latest values for the keys in spiking_sensors and
        possibly "aqi", "pm25", "pm10", "temp", "humidity" and the index fields.

    aqi_trend:
        Optional dict describing AQI tendency to peak. See _build_trend_sentence.

    forecast_window_minutes:
        Optional horizon in minutes that describes how far ahead the AI looked.

    Returns:
        (subject, plain_text_body, html_body_or_none)
    """
    sensor_list = list(spiking_sensors)
    if not sensor_list:
        subject = "Air quality update from your monitor"
        body = (
            "Your air quality monitor did not detect any clear spikes but requested "
            "an update email. No action is required right now."
        )
        return subject, body, None

    # Subject
    if "aqi" in sensor_list and len(sensor_list) == 1:
        subject = "Alert: AQI has spiked on your air quality monitor"
    elif "aqi" in sensor_list:
        subject = "Alert: AQI and other sensors have spiked on your monitor"
    else:
        subject = "Alert: One or more sensors have spiked on your monitor"

    # Heading and spike summary
    lines: List[str] = []
    lines.append("Hello,")
    lines.append("")
    lines.append(
        "Your air quality monitor has detected a spike in the following sensors:"
    )
    lines.append("")

    for sensor_key in sensor_list:
        lines.append(_format_spike_line(sensor_key, metrics))

    lines.append("")

    trend_sentence = _build_trend_sentence(aqi_trend, forecast_window_minutes)
    if trend_sentence:
        lines.append(trend_sentence)
        lines.append("")

    tips = _build_safety_tips(sensor_list)
    if tips:
        lines.append("Suggested actions:")
        for tip in tips:
            lines.append(f"- {tip}")
        lines.append("")

    lines.append("This message was generated automatically by your monitoring system.")
    lines.append("If you continue to receive alerts frequently, consider adjusting your")
    lines.append("notification settings or inspecting your environment for issues.")
    lines.append("")
    lines.append("Stay safe,")

    plain_body = "\n".join(lines)

    # Optional HTML body
    html_lines: List[str] = []
    html_lines.append("<html><body>")
    html_lines.append("<p>Hello,</p>")
    html_lines.append(
        "<p>Your air quality monitor has detected a spike in the following sensors:</p>"
    )
    html_lines.append("<ul>")
    for sensor_key in sensor_list:
        label = _sensor_display_name(sensor_key)
        value_str = _format_value(metrics.get(sensor_key) if metrics else None)
        html_lines.append(
            f"<li><strong>{label}</strong>: {value_str} (spike detected)</li>"
        )
    html_lines.append("</ul>")

    if trend_sentence:
        html_lines.append(f"<p>{trend_sentence}</p>")

    if tips:
        html_lines.append("<p>Suggested actions:</p>")
        html_lines.append("<ul>")
        for tip in tips:
            html_lines.append(f"<li>{tip}</li>")
        html_lines.append("</ul>")

    html_lines.append(
        "<p>This message was generated automatically by your monitoring system.</p>"
    )
    html_lines.append(
        "<p>If you receive alerts frequently, consider adjusting your notification "
        "settings or inspecting your environment.</p>"
    )
    html_lines.append("<p>Stay safe,</p>")
    html_lines.append("</body></html>")

    html_body = "\n".join(html_lines)

    return subject, plain_body, html_body
