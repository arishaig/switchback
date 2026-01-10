"""Time period definitions and mapping logic."""

from enum import Enum
from datetime import datetime


class TimePeriod(Enum):
    """Time periods for wallpaper switching."""

    NIGHT = "night"
    MORNING = "morning"
    AFTERNOON = "afternoon"


def get_current_period(sun_times: dict, current_time: datetime) -> TimePeriod:
    """
    Determine the current time period based on sun position.

    Args:
        sun_times: Dictionary with 'sunrise', 'noon', 'sunset' datetime objects
        current_time: Current datetime (timezone-aware)

    Returns:
        TimePeriod enum value
    """
    sunrise = sun_times['sunrise']
    sunset = sun_times['sunset']
    solar_noon = sun_times['noon']

    # Night: before sunrise OR after sunset
    if current_time < sunrise or current_time >= sunset:
        return TimePeriod.NIGHT
    # Morning: sunrise to solar noon
    elif current_time < solar_noon:
        return TimePeriod.MORNING
    # Afternoon: solar noon to sunset
    else:
        return TimePeriod.AFTERNOON
