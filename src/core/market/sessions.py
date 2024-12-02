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
        self.logger.info(f"""
        ================ SESSION CHECK START ================
        Session: {session}
        Current Time: {datetime.now()}
        UTC Time: {datetime.now(ZoneInfo("UTC"))}
        Server Time: {datetime.now(ZoneInfo("Europe/Kiev"))}  # EET timezone
        """)
        
        if session not in self.sessions:
            self.logger.error(f"Session {session} not found in configuration")
            return False

        now = datetime.now(ZoneInfo("UTC"))
        
        # Log detailed time information
        self.logger.info(f"""
        Time Check:
        Current UTC: {now}
        Weekday: {now.weekday()} ({now.strftime('%A')})
        Hour: {now.hour}
        Minute: {now.minute}
        Session Config: {self.sessions[session]}
        
        Time Conversions:
        - UTC: {now}
        - Local: {datetime.now()}
        - Server (EET): {datetime.now(ZoneInfo("Europe/Kiev"))}
        """)
        
        # Weekend check with special Sydney handling
        if now.weekday() >= 5:  # 5 is Saturday, 6 is Sunday
            self.logger.info(f"Weekend Check - Day: {now.weekday()}")
            
            if now.weekday() == 6:  # Sunday
                if session == "Sydney" and now.hour >= 21:
                    self.logger.info("Sunday after 21:00 UTC - Sydney session OPEN")
                    return True
                elif session == "Tokyo" and now.hour >= 22:
                    self.logger.info("Sunday after 22:00 UTC - Tokyo session OPEN")
                    return True
                else:
                    self.logger.info(f"Sunday but conditions not met for {session}")
                    self.logger.info(f"Hour: {now.hour}, Required: >= 21 for Sydney, >= 22 for Tokyo")
            
            self.logger.info(f"Weekend restriction applies for {session}")
            return False
                
        # Holiday check
        if self.is_holiday(session):
            self.logger.info(f"Holiday detected for {session}")
            return False

        # Session time check
        session_times = self.sessions[session]
        open_time = datetime.strptime(session_times["open"], "%H:%M").time()
        close_time = datetime.strptime(session_times["close"], "%H:%M").time()
        current_time = now.time()

        self.logger.info(f"""
        Session Time Check:
        Open Time: {open_time}
        Close Time: {close_time}
        Current Time: {current_time}
        Timezone: UTC
        Is Cross-Midnight: {open_time > close_time}
        """)

        # Handle sessions that cross midnight
        is_open = False
        if open_time > close_time:
            is_open = current_time >= open_time or current_time <= close_time
            self.logger.info(f"Cross-midnight session check: {is_open}")
        else:
            is_open = open_time <= current_time <= close_time
            self.logger.info(f"Same-day session check: {is_open}")

        self.logger.info(f"""
        ================ SESSION CHECK END ================
        Session: {session}
        Final Status: {'OPEN' if is_open else 'CLOSED'}
        """)
        
        return is_open

    def get_current_session_info(self) -> Dict:
        """Get comprehensive session information with weekend handling"""
        self.logger.info(f"\n=== Session Info Calculation Start ===")
        now = datetime.now(ZoneInfo("UTC"))
        self.logger.info(f"""
        Current UTC: {now}
        Weekday: {now.strftime('%A')}
        Hour: {now.hour}::{now.minute}
        """)

        active_sessions = []
        upcoming_sessions = []

        # Check each session
        for session in ['Sydney', 'Tokyo', 'London', 'NewYork']:
            if self.is_session_open(session):
                active_sessions.append(session)
            else:
                # Calculate time until session opens
                minutes_until = self._calculate_minutes_until(now.time(), 
                    datetime.strptime(self.sessions[session]['open'], '%H:%M').time())
                if minutes_until is not None:
                    upcoming_sessions.append({
                        'name': session,
                        'opens_in': f"{minutes_until // 60}h {minutes_until % 60}m"
                    })

        # Special handling for Sunday after 21:00 UTC
        if now.weekday() == 6 and now.hour >= 21:  # Sunday after 21:00 UTC
            self.logger.info("Sunday after 21:00 UTC - Sydney/Tokyo sessions should be active")
            if 'Sydney' not in active_sessions and now.hour >= 21:
                active_sessions.append('Sydney')
            if 'Tokyo' not in active_sessions and now.hour >= 22:
                active_sessions.append('Tokyo')

        result = {
            'active_sessions': active_sessions,
            'upcoming_sessions': upcoming_sessions,
            'market_status': 'OPEN' if active_sessions else 'CLOSED - Weekend'
        }

        self.logger.info(f"Final result: {result}")
        return result

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
        """Calculate minutes until target time, accounting for weekends and market hours"""
        try:
            now = datetime.now(ZoneInfo("UTC"))
            current_minutes = current.hour * 60 + current.minute
            target_minutes = target.hour * 60 + target.minute
            
            self.logger.info(f"""
            === Minutes Until Calculation ===
            Current UTC: {now}
            Current Day: {now.strftime('%A')}
            Current Time: {current.strftime('%H:%M')}
            Target Time: {target.strftime('%H:%M')}
            Current Minutes: {current_minutes}
            Target Minutes: {target_minutes}
            """)

            if now.weekday() == 5:  # Saturday
                hours_until_sydney = 24 + 21
                minutes_until_sydney = (hours_until_sydney * 60) - (current.hour * 60 + current.minute)
                self.logger.info(f"Saturday calculation - Minutes until Sydney: {minutes_until_sydney}")

                if target.hour == 21:  # Sydney
                    return minutes_until_sydney
                elif target.hour == 0:  # Tokyo
                    self.logger.info(f"Tokyo calculation - Adding 180 minutes to Sydney open")
                    return minutes_until_sydney + 180
                elif target.hour == 8:  # London
                    self.logger.info(f"London calculation - Adding 660 minutes to Sydney open")
                    return minutes_until_sydney + 660
                elif target.hour == 13:  # New York
                    self.logger.info(f"New York calculation - Adding 960 minutes to Sydney open")
                    return minutes_until_sydney + 960
                    
            elif now.weekday() == 6:  # Sunday
                self.logger.info(f"Sunday calculation - Hour: {now.hour}")
                if now.hour < 21:
                    minutes_until_sydney = (21 - now.hour) * 60 - now.minute
                    self.logger.info(f"Before Sydney - Minutes until: {minutes_until_sydney}")

                    if target.hour == 21:  # Sydney
                        return minutes_until_sydney
                    elif target.hour == 0:  # Tokyo
                        return minutes_until_sydney + 180
                    elif target.hour == 8:  # London
                        return minutes_until_sydney + 660
                    elif target.hour == 13:  # New York
                        return minutes_until_sydney + 960
                else:
                    self.logger.info("After Sydney open - Normal calculation")
                    if target_minutes <= current_minutes:
                        target_minutes += 24 * 60
                    minutes_until = target_minutes - current_minutes
                    self.logger.info(f"Normal calculation result: {minutes_until}")
                    return minutes_until
            else:
                self.logger.info("Weekday calculation")
                if target_minutes <= current_minutes:
                    target_minutes += 24 * 60
                minutes_until = target_minutes - current_minutes
                self.logger.info(f"Weekday calculation result: {minutes_until}")
                return minutes_until
                    
        except Exception as e:
            self.logger.error(f"Error calculating session time: {str(e)}")
            return 0