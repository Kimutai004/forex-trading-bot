# In core/trading_logic.py

from typing import Dict, Optional
from datetime import datetime
import logging
from src.signals.providers.base import Signal, SignalType
import traceback
import MetaTrader5 as mt5
import json

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
        """Setup centralized logging for trading logic"""
        from src.utils.logger import setup_logger, get_implementation_logger
        self.logger = setup_logger('TradingLogic')
        impl_logger = get_implementation_logger()
        impl_logger.info("TradingLogic logging configured with centralized system")
        
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
            self.logger.info(f"""
            =================== POSITION MONITORING START ===================
            Current Time: {datetime.now()}
            Total Positions: {len(positions)}
            Market Status: {'OPEN' if self.mt5_trader.market_is_open else 'CLOSED'}
            ===========================================================
            """)
            
            for position in positions:
                try:
                    # Log position details before duration check
                    self.logger.info(f"""
                    Checking Position:
                    - Ticket: {position['ticket']}
                    - Symbol: {position['symbol']}
                    - Type: {position['type']}
                    - Open Time: {position['time']}
                    - Current Time: {datetime.now()}
                    """)
                    
                    # Only use FTMO manager's duration check
                    duration_check = self.ftmo_manager.check_position_duration(position)
                    
                    self.logger.info(f"""
                    Duration Check Results:
                    - Position: {position['ticket']}
                    - Symbol: {position['symbol']}
                    - Duration: {duration_check['duration']}
                    - Max Allowed: {duration_check['max_duration']}min
                    - Needs Closure: {duration_check['needs_closure']}
                    - Warning Active: {duration_check['warning']}
                    """)
                    
                    if duration_check['warning']:
                        self.logger.warning(f"""
                        DURATION WARNING:
                        - Position: {position['ticket']}
                        - Symbol: {position['symbol']}
                        - Current Duration: {duration_check['duration']}
                        """)
                    
                    if duration_check['needs_closure']:
                        self.logger.warning(f"""
                        DURATION EXCEEDED - ATTEMPTING CLOSURE:
                        - Position: {position['ticket']}
                        - Symbol: {position['symbol']}
                        - Final Duration: {duration_check['duration']}
                        """)
                        
                        # Try to close position
                        success, message = self.position_manager.close_position(position['ticket'])
                        
                        self.logger.info(f"""
                        Position Closure Attempt:
                        - Ticket: {position['ticket']}
                        - Success: {success}
                        - Message: {message}
                        - Market Status: {'OPEN' if self.mt5_trader.market_is_open else 'CLOSED'}
                        """)
                        
                except Exception as e:
                    self.logger.error(f"""
                    Position Monitoring Error:
                    - Position: {position.get('ticket', 'unknown')}
                    - Error: {str(e)}
                    - Traceback: {traceback.format_exc()}
                    """)
                    continue
                    
        except Exception as e:
            self.logger.error(f"""
            Position Monitoring Critical Error:
            Error: {str(e)}
            Traceback: {traceback.format_exc()}
            """)

    def process_symbol(self, symbol: str) -> Optional[Dict]:
        """Process trading logic for a symbol"""
        try:
            self.logger.info(f"""
            =============== TRADE PROCESSING START ===============
            Symbol: {symbol}
            Time: {datetime.now()}
            Market Status: {self.mt5_trader.market_is_open}
            """)
            
            # Get market state 
            market_state = self.mt5_trader.log_market_state()
            
            # Get all signals for the symbol
            signals = self.signal_manager.get_signals(symbol)
            self.logger.info(f"""
            Signal Check:
            - Total Signals: {len(signals) if signals else 0}
            - Market Session: {market_state.get('session', 'Unknown')}
            - Market Active: {market_state.get('market_active', False)}
            """)
            
            if not signals:
                return None
                
            # Get consensus signal (strong agreement among providers)
            consensus = self.signal_manager.get_consensus_signal(symbol)
            if not consensus or consensus.type == SignalType.NONE:
                return None
                
            # Log signal strength calculation
            signal_strength = len([s for s in signals if s.type == consensus.type]) / len(signals)
            self.logger.info(f"""
            Signal Analysis:
            - Consensus Type: {consensus.type}
            - Signal Strength: {signal_strength:.2f}
            - Required Strength: {self.required_signal_strength}
            """)
            
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
            
            self.logger.info(f"""
            Trade Preparation:
            - Symbol: {symbol}
            - Type: {consensus.type.value}
            - Volume: {volume}
            - Entry: {consensus.entry_price}
            - SL: {consensus.stop_loss}
            - TP: {consensus.take_profit}
            - Server Time: {datetime.fromtimestamp(mt5.symbol_info_tick(symbol).time if mt5.symbol_info_tick(symbol) else 0)}
            - Raw Server Time: {mt5.symbol_info_tick(symbol).time if mt5.symbol_info_tick(symbol) else 0}
            """)
            
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
            
            self.logger.info(f"""
            Trade Execution Result:
            - Success: {success}
            - Message: {message}
            - Execution Time: {datetime.now()}
            =============== TRADE PROCESSING END ===============
            """)
            
            if success:
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
            self.logger.error(f"""
            Trade Processing Error:
            Symbol: {symbol}
            Error: {str(e)}
            Traceback: {traceback.format_exc()}
            """)
            return None
    
    def execute_trade(self, decision: Dict) -> bool:
        """Execute trading decision"""
        try:
            self.logger.info(f"""
            ================== TRADE EXECUTION START ==================
            Time: {datetime.now()}
            Decision Parameters: {json.dumps(decision, default=str, indent=2)}
            Market Status: {self.mt5_trader.market_is_open}
            """)

            if not decision or not decision['signal']:
                self.logger.info("No valid decision or signal")
                return False
                
            signal = decision['signal']
            symbol = decision['symbol']
            current_positions = decision['open_positions']
            
            if current_positions > 0:
                self.logger.info(f"Already have {current_positions} positions for {symbol}")
                return False
                
            if signal.type not in [SignalType.BUY, SignalType.SELL]:
                self.logger.info(f"Invalid signal type: {signal.type}")
                return False
                    
            volume = signal.volume or 0.01
                
            success, message = self.mt5_trader.place_trade(
                symbol=symbol,
                order_type=signal.type.value,
                volume=volume,
                price=signal.entry_price,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
                comment=f"Auto trade: {signal.type.value}"
            )
            
            self.logger.info(f"""
            Trade Execution Result:
            - Success: {success}
            - Message: {message}
            - Time: {datetime.now()}
            ================== TRADE EXECUTION END ==================
            """)
            
            if success:
                self.logger.info(f"Successfully executed {signal.type.value} trade for {symbol}")
            else:
                self.logger.error(f"Failed to execute trade: {message}")
                
            return success
                
        except Exception as e:
            self.logger.error(f"""
            Trade Execution Error:
            Error: {str(e)}
            Traceback: {traceback.format_exc()}
            """)
            return False

    def get_position_summary(self) -> Dict:
        """Get summary of current positions and trading status"""
        positions = self.position_manager.get_open_positions()
        
        return {
            'total_positions': len(positions),
            'symbols_traded': list(set(pos['symbol'] for pos in positions)),
            'total_profit': sum(pos['profit'] for pos in positions),
            'positions_available': self.max_total_positions - len(positions)
        }