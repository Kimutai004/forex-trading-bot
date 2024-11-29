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
        """Check if a trading session is currently open"""
        if session not in self.sessions:
            return False

        now = datetime.now(ZoneInfo("UTC"))
        
        # Check for holidays
        if self.is_holiday(session):
            return False

        session_times = self.sessions[session]
        open_time = datetime.strptime(session_times["open"], "%H:%M").time()
        close_time = datetime.strptime(session_times["close"], "%H:%M").time()
        current_time = now.time()

        # Handle sessions that cross midnight
        if open_time > close_time:
            return current_time >= open_time or current_time <= close_time
        else:
            return open_time <= current_time <= close_time

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
        """Calculate minutes until target time"""
        current_minutes = current.hour * 60 + current.minute
        target_minutes = target.hour * 60 + target.minute
        
        if target_minutes <= current_minutes:
            target_minutes += 24 * 60
            
        return target_minutes - current_minutes