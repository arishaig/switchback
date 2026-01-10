"""Transition tracking for gradual wallpaper changes."""

import logging
from datetime import datetime, timedelta

from switchback.sun_calculator import SunCalculator
from switchback.time_period import TimePeriod


logger = logging.getLogger(__name__)


class TransitionTracker:
    """Tracks period transitions and calculates blend states."""

    def __init__(self, sun_calc: SunCalculator):
        """
        Initialize transition tracker.

        Args:
            sun_calc: SunCalculator instance for calculating sun times
        """
        self.sun_calc = sun_calc

    def get_period_boundaries(
        self,
        current_time: datetime,
        current_period: TimePeriod
    ) -> tuple[datetime, datetime]:
        """
        Get start and end times for current period.

        Args:
            current_time: Current datetime (timezone-aware)
            current_period: Current TimePeriod

        Returns:
            (period_start, period_end) datetimes
        """
        sun_times = self.sun_calc.get_sun_times(current_time)
        sunrise = sun_times['sunrise']
        noon = sun_times['noon']
        sunset = sun_times['sunset']

        if current_period == TimePeriod.NIGHT:
            # Night can span midnight, need special handling
            if current_time < sunrise:
                # Night before sunrise: yesterday's sunset → today's sunrise
                yesterday = current_time - timedelta(days=1)
                yesterday_sun = self.sun_calc.get_sun_times(yesterday)
                period_start = yesterday_sun['sunset']
                period_end = sunrise
                logger.debug(
                    f"Night period (before sunrise): {period_start.strftime('%H:%M')} → "
                    f"{period_end.strftime('%H:%M')}"
                )
            else:
                # Night after sunset: today's sunset → tomorrow's sunrise
                tomorrow = current_time + timedelta(days=1)
                tomorrow_sun = self.sun_calc.get_sun_times(tomorrow)
                period_start = sunset
                period_end = tomorrow_sun['sunrise']
                logger.debug(
                    f"Night period (after sunset): {period_start.strftime('%H:%M')} → "
                    f"{period_end.strftime('%H:%M')} (next day)"
                )

            return (period_start, period_end)

        elif current_period == TimePeriod.MORNING:
            logger.debug(
                f"Morning period: {sunrise.strftime('%H:%M')} → {noon.strftime('%H:%M')}"
            )
            return (sunrise, noon)

        else:  # AFTERNOON
            logger.debug(
                f"Afternoon period: {noon.strftime('%H:%M')} → {sunset.strftime('%H:%M')}"
            )
            return (noon, sunset)

    def get_transition_wallpapers(
        self,
        current_period: TimePeriod
    ) -> tuple[str, str]:
        """
        Get the FROM and TO wallpaper periods for current transition.

        During each period, we gradually transition FROM the period's wallpaper
        TO the next period's wallpaper.

        Args:
            current_period: Current TimePeriod

        Returns:
            (from_period, to_period) strings
        """
        if current_period == TimePeriod.NIGHT:
            # Night transitions TO morning
            return ("night", "morning")
        elif current_period == TimePeriod.MORNING:
            # Morning transitions TO afternoon
            return ("morning", "afternoon")
        else:  # AFTERNOON
            # Afternoon transitions TO night
            return ("afternoon", "night")
