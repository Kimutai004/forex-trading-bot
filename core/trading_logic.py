# In core/trading_logic.py

from typing import Dict, Optional
from datetime import datetime
import logging
from signals.signal_provider import Signal, SignalType

class TradingLogic:
    """Handles automated trading decisions and execution"""
    
    def __init__(self, mt5_trader, signal_manager, position_manager, ftmo_manager=None):
        """
        Initialize Trading Logic
        
        Args:
            mt5_trader: MT5Trader instance for trade execution
            signal_manager: SignalManager for getting trading signals
            position_manager: PositionManager for position handling
            ftmo_manager: FTMORuleManager instance for trade rules
        """
        self.mt5_trader = mt5_trader
        self.signal_manager = signal_manager
        self.position_manager = position_manager
        self.ftmo_manager = ftmo_manager
        self._setup_logging()
        
        # Trading parameters
        self.min_risk_reward = 2.0
        self.max_positions_per_symbol = 1
        self.max_total_positions = 3
        self.required_signal_strength = 0.7

    def _setup_logging(self):
        """Setup logging for trading logic"""
        self.logger = logging.getLogger('TradingLogic')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def check_position_duration(self, position: Dict) -> Dict:
        """
        Check if position has exceeded maximum duration
        
        Args:
            position: Position dictionary from PositionManager
            
        Returns:
            Dict with status and duration information
        """
        try:
            current_time = datetime.now()
            max_duration = self.rules['time_rules']['max_position_duration']  # in minutes
            
            # Calculate position duration
            open_time = datetime.fromtimestamp(position['open_timestamp'])
            duration = current_time - open_time
            duration_minutes = duration.total_seconds() / 60
            
            # Format duration string with full date if over 24 hours
            if duration.total_seconds() >= 86400:  # 24 hours in seconds
                duration_str = open_time.strftime('%Y-%m-%d %H:%M:%S')
            else:
                hours = int(duration_minutes // 60)
                minutes = int(duration_minutes % 60)
                duration_str = f"{hours}h {minutes}m"

            return {
                'needs_closure': duration_minutes >= max_duration,
                'duration': duration_str,
                'duration_minutes': duration_minutes,
                'max_duration': max_duration,
                'open_time': open_time.strftime('%Y-%m-%d %H:%M:%S'),
                'warning': duration_minutes >= (max_duration * 0.75)  # Warning at 75% of max duration
            }
        except Exception as e:
            self.logger.error(f"Error checking position duration: {str(e)}")
            return {
                'needs_closure': False,
                'duration': "0h 0m",
                'duration_minutes': 0,
                'max_duration': max_duration,
                'open_time': "Unknown",
                'warning': False
            }
        
    def _validate_trading_conditions(self, symbol: str, signal: Signal) -> bool:
        """Validate if trading conditions are met"""
        # Check if we already have maximum positions
        current_positions = self.position_manager.get_open_positions()
        if len(current_positions) >= self.max_total_positions:
            self.logger.info(f"Maximum total positions ({self.max_total_positions}) reached")
            return False
            
        # Check symbol-specific position limit
        symbol_positions = [p for p in current_positions if p['symbol'] == symbol]
        if len(symbol_positions) >= self.max_positions_per_symbol:
            self.logger.info(f"Maximum positions for {symbol} reached")
            return False
            
        # Calculate Risk/Reward ratio
        if signal.entry_price and signal.stop_loss and signal.take_profit:
            risk = abs(signal.entry_price - signal.stop_loss)
            reward = abs(signal.take_profit - signal.entry_price)
            rr_ratio = reward / risk if risk > 0 else 0
            
            if rr_ratio < self.min_risk_reward:
                self.logger.info(f"Risk/Reward ratio ({rr_ratio:.2f}) below minimum ({self.min_risk_reward})")
                return False
        
        return True
    
    def monitor_positions(self):
        """Monitor and enforce position duration limits"""
        try:
            if not self.ftmo_manager:
                self.logger.error("FTMO manager not initialized")
                return
                
            if not self.mt5_trader.market_is_open:
                self.logger.warning("Market is closed - will attempt position closure when market opens")
                return

            positions = self.position_manager.get_open_positions()
            self.logger.info(f"[Duration Monitor] Checking {len(positions)} positions for time limits")
            
            for position in positions:
                try:
                    duration_check = self.ftmo_manager.check_position_duration(position)
                    
                    self.logger.info(
                        f"[Duration Check] Position {position['ticket']} ({position['symbol']}) "
                        f"Duration: {duration_check['duration']} | "
                        f"Max allowed: {duration_check['max_duration']}min | "
                        f"Needs closure: {duration_check['needs_closure']}"
                    )
                    
                    if duration_check['warning']:
                        self.logger.warning(
                            f"[Duration Warning] Position {position['ticket']} ({position['symbol']}) "
                            f"approaching time limit - Current duration: {duration_check['duration']}"
                        )
                    
                    if duration_check['needs_closure']:
                        self.logger.warning(
                            f"[Duration Exceeded] Position {position['ticket']} ({position['symbol']}) "
                            f"exceeded maximum duration. Current: {duration_check['duration']}"
                        )
                        
                        # Try to close position
                        success, message = self.position_manager.close_position(position['ticket'])
                        
                        if success:
                            self.logger.info(
                                f"[Closure Success] Position {position['ticket']} closed successfully"
                            )
                        else:
                            if "10018" in message:  # Market closed error
                                self.logger.warning(
                                    f"[Closure Delayed] Market closed for {position['symbol']}. "
                                    f"Will attempt closure when market opens"
                                )
                            else:
                                self.logger.error(
                                    f"[Closure Failed] Failed to close position {position['ticket']}. "
                                    f"Error: {message}"
                                )
                            
                except Exception as e:
                    self.logger.error(f"[Monitor Error] Error monitoring position {position.get('ticket', 'unknown')}: {str(e)}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"[Monitor Error] Error in position monitoring: {str(e)}")

    def process_symbol(self, symbol: str) -> Optional[Dict]:
        """Process trading logic for a symbol"""
        try:
            # Get all signals for the symbol
            signals = self.signal_manager.get_signals(symbol)
            if not signals:
                return None
                
            # Get consensus signal (strong agreement among providers)
            consensus = self.signal_manager.get_consensus_signal(symbol)
            if not consensus or consensus.type == SignalType.NONE:
                return None
                
            # Check if we have a strong enough signal
            signal_strength = len([s for s in signals if s.type == consensus.type]) / len(signals)
            if signal_strength < self.required_signal_strength:
                self.logger.info(f"Signal strength ({signal_strength:.2f}) below required ({self.required_signal_strength})")
                return None
                
            # Validate trading conditions
            if not self._validate_trading_conditions(symbol, consensus):
                return None
                
            # Prepare trade parameters
            volume = consensus.volume or 0.01  # Default to minimum if not specified
            
            # Create a simple comment without special characters
            comment = f"MT5Bot_{consensus.type.value}"
            
            # Execute the trade
            success, message = self.mt5_trader.place_trade(
                symbol=symbol,
                order_type=consensus.type.value,
                volume=volume,
                price=consensus.entry_price,
                stop_loss=consensus.stop_loss,
                take_profit=consensus.take_profit,
                comment=comment
            )
            
            if success:
                self.logger.info(f"Trade executed for {symbol}: {message}")
                return {
                    'symbol': symbol,
                    'signal': consensus,
                    'execution': 'success',
                    'message': message
                }
            else:
                self.logger.error(f"Trade execution failed: {message}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error processing {symbol}: {str(e)}")
            return None

    def get_position_summary(self) -> Dict:
        """Get summary of current positions and trading status"""
        positions = self.position_manager.get_open_positions()
        
        return {
            'total_positions': len(positions),
            'symbols_traded': list(set(pos['symbol'] for pos in positions)),
            'total_profit': sum(pos['profit'] for pos in positions),
            'positions_available': self.max_total_positions - len(positions)
        }