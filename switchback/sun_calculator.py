"""Sun position calculation using astral library."""

import logging
from datetime import datetime, time, timedelta
from astral import LocationInfo
from astral.sun import sun
import pytz


logger = logging.getLogger(__name__)


class SunCalculator:
    """Calculate sun position for a given location."""

    def __init__(self, latitude: float, longitude: float, timezone: str):
        """
        Initialize sun calculator.

        Args:
            latitude: Latitude in degrees (-90 to 90)
            longitude: Longitude in degrees (-180 to 180)
            timezone: IANA timezone string (e.g., 'US/Pacific')
        """
        self.location = LocationInfo(
            latitude=latitude,
            longitude=longitude,
            timezone=timezone
        )
        self.tz = pytz.timezone(timezone)

    def get_sun_times(self, date: datetime = None) -> dict:
        """
        Get sun times for a specific date.

        Args:
            date: Date to calculate for (defaults to today)

        Returns:
            Dictionary with 'sunrise', 'noon', 'sunset' as timezone-aware datetime objects
        """
        if date is None:
            date = datetime.now(self.tz)

        try:
            sun_times = sun(self.location.observer, date=date.date(), tzinfo=self.tz)
            return {
                'sunrise': sun_times['sunrise'],
                'noon': sun_times['noon'],
                'sunset': sun_times['sunset'],
            }
        except ValueError as e:
            # Polar regions where sun doesn't rise/set
            logger.warning(f"Sun calculation failed (polar region?): {e}. Using fallback times.")
            return self._time_based_fallback(date)

    def _time_based_fallback(self, date: datetime) -> dict:
        """
        Fallback for polar regions where sun doesn't rise/set.

        Uses fixed times: 6am (sunrise), 12pm (noon), 6pm (sunset)

        Args:
            date: Date to create fallback times for

        Returns:
            Dictionary with 'sunrise', 'noon', 'sunset'
        """
        day = date.date()
        return {
            'sunrise': self.tz.localize(datetime.combine(day, time(6, 0))),
            'noon': self.tz.localize(datetime.combine(day, time(12, 0))),
            'sunset': self.tz.localize(datetime.combine(day, time(18, 0))),
        }

    def get_next_transition_time(self, current_time: datetime, current_period: str) -> datetime:
        """
        Calculate when the next period transition occurs.

        Args:
            current_time: Current datetime (timezone-aware)
            current_period: Current period name ('night', 'morning', 'afternoon')

        Returns:
            Datetime of next transition
        """
        sun_times = self.get_sun_times(current_time)
        sunrise = sun_times['sunrise']
        noon = sun_times['noon']
        sunset = sun_times['sunset']

        if current_period == 'night' and current_time < sunrise:
            # Night before sunrise → wait for sunrise
            return sunrise
        elif current_period == 'morning':
            # Morning → wait for solar noon
            return noon
        elif current_period == 'afternoon':
            # Afternoon → wait for sunset
            return sunset
        else:
            # Night after sunset → wait for tomorrow's sunrise
            tomorrow = current_time.date() + timedelta(days=1)
            tomorrow_sun = self.get_sun_times(
                self.tz.localize(datetime.combine(tomorrow, time(0, 0)))
            )
            return tomorrow_sun['sunrise']
