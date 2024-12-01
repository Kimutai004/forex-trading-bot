import json
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo
import os

class MarketSessionManager:
    def __init__(self, config_dir: str = "config"):
        """Initialize market session manager with calendar data"""
        self.config_dir = config_dir
        self.calendar_file = os.path.join(config_dir, "market_calendar.json")
        self.calendar_data = self._load_calendar()
        self.sessions = self.calendar_data.get("sessions", {})
        self.holidays = self.calendar_data.get("holidays", {})
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging for market session manager"""
        from src.utils.logger import setup_logger
        self.logger = setup_logger('MarketSessionManager')
        self.logger.info("MarketSessionManager initialized with logging")

    def _load_calendar(self) -> Dict:
        """Load market calendar from JSON file"""
        try:
            with open(self.calendar_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {"sessions": {}, "holidays": {}}

    def is_holiday(self, session: str, date: Optional[datetime] = None) -> bool:
        """Check if given date is a holiday for the specified session"""
        if date is None:
            date = datetime.now()

        year = str(date.year)
        date_str = date.strftime("%Y-%m-%d")

        if year in self.holidays and session in self.holidays[year]:
            return any(holiday["date"] == date_str 
                      for holiday in self.holidays[year][session])
        return False

    def is_session_open(self, session: str) -> bool:
        """Check if a trading session is currently open with enhanced logging"""
        from src.utils.logger import setup_logger
        logger = setup_logger('MarketSessionManager')
        
        logger.info(f"Checking if session {session} is open...")
        
        if session not in self.sessions:
            logger.warning(f"Session {session} not found in configuration")
            return False

        now = datetime.now(ZoneInfo("UTC"))
        logger.info(f"Current UTC time: {now}")
        
        # Check for weekend
        if now.weekday() >= 5:  # 5 is Saturday, 6 is Sunday
            logger.warning(f"Market should be closed - Current day is {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][now.weekday()]}")
            return False
            
        # Check for holidays
        if self.is_holiday(session):
            logger.warning(f"Market should be closed - Holiday detected for session {session}")
            return False

        session_times = self.sessions[session]
        open_time = datetime.strptime(session_times["open"], "%H:%M").time()
        close_time = datetime.strptime(session_times["close"], "%H:%M").time()
        current_time = now.time()

        logger.info(f"Session times - Open: {open_time}, Close: {close_time}, Current: {current_time}")

        # Handle sessions that cross midnight
        is_open = False
        if open_time > close_time:
            is_open = current_time >= open_time or current_time <= close_time
        else:
            is_open = open_time <= current_time <= close_time

        logger.info(f"Session {session} status: {'Open' if is_open else 'Closed'}")
        return is_open

    def get_current_session_info(self) -> Dict:
        """Get comprehensive session information"""
        now = datetime.now(ZoneInfo("UTC"))
        active_sessions = []
        upcoming_sessions = []

        # Check active sessions
        for session in self.sessions:
            if self.is_session_open(session):
                active_sessions.append(session)

        # Calculate upcoming sessions, including holiday-affected ones
        for session, times in self.sessions.items():
            if session not in active_sessions:
                open_time = datetime.strptime(times["open"], "%H:%M").time()
                minutes_until = self._calculate_minutes_until(now.time(), open_time)
                
                # Adjust for holidays
                if self.is_holiday(session):
                    next_opening = now + timedelta(days=1)
                    while self.is_holiday(session, next_opening):
                        next_opening += timedelta(days=1)
                        minutes_until += 24 * 60  # Add a day's worth of minutes

                upcoming_sessions.append({
                    'name': session,
                    'opens_in': f"{minutes_until // 60}h {minutes_until % 60}m"
                })

        # Sort upcoming sessions by time until opening
        upcoming_sessions.sort(key=lambda x: self._parse_time_string(x['opens_in']))

        return {
            'active_sessions': active_sessions,
            'upcoming_sessions': upcoming_sessions
        }

    def _parse_time_string(self, time_str: str) -> int:
        """Convert time string (e.g., '6h 30m') to minutes"""
        hours = int(time_str.split('h')[0])
        minutes = int(time_str.split('h')[1].strip().split('m')[0])
        return hours * 60 + minutes

    def _calculate_minutes_until(self, current: time, target: time) -> int:
        """
        Calculate minutes until target time, accounting for weekends and market hours
        
        Args:
            current: Current time
            target: Target session opening time
            
        Returns:
            int: Minutes until next session
        """
        try:
            now = datetime.now(ZoneInfo("UTC"))
            current_minutes = current.hour * 60 + current.minute
            target_minutes = target.hour * 60 + target.minute
            
            self.logger.info(f"""
            Calculating next session time:
            Current UTC: {now}
            Current Day: {now.strftime('%A')}
            Target Time: {target.strftime('%H:%M')}
            Current Minutes: {current_minutes}
            Target Minutes: {target_minutes}
            """)

            if now.weekday() == 5:  # Saturday
                # Calculate minutes until Sunday 21:00 UTC (Sydney open)
                hours_until_sydney = 24 + 21  # 24 hours until Sunday + 21 hours until Sydney open
                minutes_until_sydney = (hours_until_sydney * 60) - (current.hour * 60 + current.minute)
                
                self.logger.info(f"Saturday: Minutes until Sydney open: {minutes_until_sydney}")

                if target.hour == 21:  # Sydney
                    return minutes_until_sydney
                elif target.hour == 0:  # Tokyo (next day)
                    return minutes_until_sydney + 180  # Sydney + 3 hours
                elif target.hour == 8:  # London
                    return minutes_until_sydney + 660  # Sydney + 11 hours
                elif target.hour == 13:  # New York
                    return minutes_until_sydney + 960  # Sydney + 16 hours
                    
            elif now.weekday() == 6:  # Sunday
                if now.hour < 21:  # Before Sydney open
                    # Minutes until Sydney open
                    minutes_until_sydney = (21 - now.hour) * 60 - now.minute
                    
                    self.logger.info(f"Sunday before Sydney: Minutes until Sydney open: {minutes_until_sydney}")

                    if target.hour == 21:  # Sydney
                        return minutes_until_sydney
                    elif target.hour == 0:  # Tokyo (next day)
                        return minutes_until_sydney + 180  # Sydney + 3 hours
                    elif target.hour == 8:  # London
                        return minutes_until_sydney + 660  # Sydney + 11 hours
                    elif target.hour == 13:  # New York
                        return minutes_until_sydney + 960  # Sydney + 16 hours
                else:
                    # After Sydney open, normal calculation
                    if target_minutes <= current_minutes:
                        target_minutes += 24 * 60
                    minutes_until = target_minutes - current_minutes
                    self.logger.info(f"Sunday after Sydney: Normal calculation: {minutes_until}")
                    return minutes_until
            else:
                # Normal weekday calculation
                if target_minutes <= current_minutes:
                    target_minutes += 24 * 60
                minutes_until = target_minutes - current_minutes
                self.logger.info(f"Weekday: Normal calculation: {minutes_until}")
                return minutes_until
                
        except Exception as e:
            self.logger.error(f"Error calculating session time: {str(e)}")
            return 0