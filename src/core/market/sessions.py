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
        """Get comprehensive session information with weekend handling"""
        now = datetime.now(ZoneInfo("UTC"))
        active_sessions = []
        upcoming_sessions = []

        # Check if it's weekend first
        if now.weekday() >= 5:  # 5 is Saturday, 6 is Sunday
            self.logger.info(f"Market closed - Weekend ({['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][now.weekday()]})")
            
            # Calculate time until market open (Sydney session on Sunday)
            if now.weekday() == 5:  # Saturday
                hours_until = 24 + 21  # 24 hours until Sunday + 21 hours until Sydney open
                minutes_until = (hours_until * 60) - (now.hour * 60 + now.minute)
            else:  # Sunday
                if now.hour < 21:  # Before Sydney open
                    minutes_until = (21 - now.hour) * 60 - now.minute
                else:
                    minutes_until = 0  # Sydney session about to open
                    
            upcoming_sessions.append({
                'name': 'Sydney (Market Open)',
                'opens_in': f"{minutes_until // 60}h {minutes_until % 60}m"
            })
            
            return {
                'active_sessions': [],
                'upcoming_sessions': upcoming_sessions,
                'market_status': 'CLOSED - Weekend'
            }

        # Regular session checks
        for session in self.sessions:
            if self.is_session_open(session):
                active_sessions.append(session)
            else:
                session_times = self.sessions[session]
                open_time = datetime.strptime(session_times["open"], "%H:%M").time()
                minutes_until = self._calculate_minutes_until(now.time(), open_time)
                if minutes_until is not None:
                    upcoming_sessions.append({
                        'name': session,
                        'opens_in': f"{minutes_until // 60}h {minutes_until % 60}m"
                    })

        # Sort upcoming sessions by time until opening
        upcoming_sessions.sort(key=lambda x: int(x['opens_in'].split('h')[0]) * 60 + int(x['opens_in'].split('h')[1].split('m')[0]))

        return {
            'active_sessions': active_sessions,
            'upcoming_sessions': upcoming_sessions,
            'market_status': 'OPEN' if active_sessions else 'CLOSED'
        }

    def _parse_time_string(self, time_str: str) -> int:
        """Convert time string (e.g., '6h 30m') to minutes"""
        hours = int(time_str.split('h')[0])
        minutes = int(time_str.split('h')[1].strip().split('m')[0])
        return hours * 60 + minutes
    
    def verify_session_configuration(self) -> Dict:
        """
        Verify all session configurations and overlap periods
        Returns Dict with verification results
        """
        try:
            self.logger.info("Verifying session configurations...")
            
            verification = {
                'sessions': {'status': 'OK', 'issues': []},
                'overlaps': {'status': 'OK', 'issues': []}
            }

            # Verify main sessions
            required_sessions = {
                'Sydney': ('22:00', '07:00'),
                'Tokyo': ('00:00', '09:00'),
                'London': ('08:00', '16:00'),
                'NewYork': ('13:00', '21:00')
            }

            for session, times in required_sessions.items():
                if session not in self.sessions:
                    verification['sessions']['status'] = 'ERROR'
                    verification['sessions']['issues'].append(f'Missing {session} session')
                    continue

                session_config = self.sessions[session]
                if session_config.get('open') != times[0] or session_config.get('close') != times[1]:
                    verification['sessions']['status'] = 'WARNING'
                    verification['sessions']['issues'].append(
                        f"{session} session times mismatch - Expected: {times}, Got: {session_config.get('open')}-{session_config.get('close')}"
                    )
                else:
                    self.logger.info(f"{session} session times verified: {times[0]}-{times[1]}")

            # Verify overlap periods
            required_overlaps = {
                'Sydney-Tokyo': ('00:00', '02:00'),
                'Tokyo-London': ('08:00', '09:00'),
                'London-NY': ('13:00', '16:00')
            }

            overlap_data = self.calendar_data.get('overlaps', {})
            for overlap, times in required_overlaps.items():
                if overlap not in overlap_data:
                    verification['overlaps']['status'] = 'WARNING'
                    verification['overlaps']['issues'].append(f'Missing {overlap} overlap configuration')
                    continue

                overlap_config = overlap_data[overlap]
                if overlap_config.get('start') != times[0] or overlap_config.get('end') != times[1]:
                    verification['overlaps']['status'] = 'WARNING'
                    verification['overlaps']['issues'].append(
                        f"{overlap} overlap times mismatch - Expected: {times}, Got: {overlap_config.get('start')}-{overlap_config.get('end')}"
                    )
                else:
                    self.logger.info(f"{overlap} overlap times verified: {times[0]}-{times[1]}")

            # Log verification results
            self.logger.info(f"""
            Session Configuration Verification Results:
            Sessions Status: {verification['sessions']['status']}
            Session Issues: {', '.join(verification['sessions']['issues']) if verification['sessions']['issues'] else 'None'}
            
            Overlaps Status: {verification['overlaps']['status']}
            Overlap Issues: {', '.join(verification['overlaps']['issues']) if verification['overlaps']['issues'] else 'None'}
            """)

            return verification

        except Exception as e:
            self.logger.error(f"Error verifying session configuration: {str(e)}")
            return {
                'sessions': {'status': 'ERROR', 'issues': [str(e)]},
                'overlaps': {'status': 'ERROR', 'issues': [str(e)]}
            }

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