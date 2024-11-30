import logging
from typing import List, Dict
from .signal_provider import SignalProvider, Signal, SignalType
from datetime import datetime


class SignalEvaluator:
    """Enhanced signal evaluation system incorporating all trading criteria"""
    
    def __init__(self, signal_manager, trading_logic, ftmo_manager=None):
        """Initialize SignalEvaluator
        
        Args:
            signal_manager: SignalManager instance
            trading_logic: TradingLogic instance
            ftmo_manager: Optional FTMORuleManager instance
        """
        self.signal_manager = signal_manager
        self.trading_logic = trading_logic
        self.ftmo_manager = ftmo_manager
        self.position_manager = trading_logic.position_manager
        self._setup_logging()
        self.logger.info("SignalEvaluator initialized with signal manager and trading logic")
        
    def _setup_logging(self):
        """Setup logging configuration"""
        self.logger = logging.getLogger('SignalEvaluator')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - [%(levelname)s] - %(message)s\n'
                'File: %(filename)s:%(lineno)d\n'
                'Function: %(funcName)s\n'
                '----------------------------------------'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.DEBUG)

    def evaluate_signal(self, symbol: str, signals: List[Signal]) -> dict:
        """
        Comprehensive signal evaluation incorporating all trading criteria
        """
        self.logger.info(f"Starting signal evaluation for {symbol}")
        
        # Create evaluation result
        evaluation = {
            'signal_strength': 0.0,
            'trading_eligible': False,
            'status': 'WEAK',
            'details': {},
            'timestamp': datetime.now()
        }
        
        try:
            if not signals:
                self.logger.info(f"No signals provided for {symbol}")
                evaluation['details']['reason'] = 'No signals available'
                return evaluation
                
            # Calculate provider consensus
            signal_counts = self._calculate_signal_counts(signals)
            self.logger.debug(f"Signal counts for {symbol}: {signal_counts}")
            
            consensus_strength = self._calculate_consensus_strength(signal_counts)
            self.logger.info(f"Calculated consensus strength for {symbol}: {consensus_strength}")
            evaluation['signal_strength'] = consensus_strength
            
            # Evaluate trading conditions
            position_check = self._check_position_limits(symbol)
            self.logger.debug(f"Position limit check for {symbol}: {position_check}")
            
            risk_reward_check = self._check_risk_reward_ratio(signals)
            self.logger.debug(f"Risk/Reward check for {symbol}: {risk_reward_check}")
            
            # Store detailed results
            evaluation['details'].update({
                'consensus_strength': consensus_strength,
                'position_limits': position_check,
                'risk_reward': risk_reward_check,
                'total_signals': len(signals)
            })
            
            # Determine final status
            evaluation.update(
                self._determine_final_status(
                    consensus_strength,
                    position_check,
                    risk_reward_check
                )
            )
            
            self.logger.info(f"Completed evaluation for {symbol}: Status={evaluation['status']}, Eligible={evaluation['trading_eligible']}")
            return evaluation
            
        except Exception as e:
            self.logger.error(f"Error during signal evaluation for {symbol}: {str(e)}", exc_info=True)
            evaluation['details']['error'] = str(e)
            return evaluation
        
    def _calculate_signal_counts(self, signals: list) -> dict:
        """Calculate the number of each signal type"""
        try:
            counts = {'BUY': 0, 'SELL': 0, 'NONE': 0}
            for signal in signals:
                counts[signal.type.value] += 1
            self.logger.debug(f"Calculated signal counts: {counts}")
            return counts
        except Exception as e:
            self.logger.error(f"Error calculating signal counts: {str(e)}")
            return {'BUY': 0, 'SELL': 0, 'NONE': 0}
        
    def _calculate_consensus_strength(self, counts: dict) -> float:
        """Calculate signal strength based on provider consensus"""
        try:
            total_signals = sum(counts.values())
            if total_signals == 0:
                self.logger.debug("No signals to calculate consensus strength")
                return 0.0
                
            max_count = max(counts.values())
            strength = max_count / total_signals
            self.logger.debug(f"Calculated consensus strength: {strength}")
            return strength
        except Exception as e:
            self.logger.error(f"Error calculating consensus strength: {str(e)}")
            return 0.0
        
    def _check_position_limits(self, symbol: str) -> dict:
        """Check if position limits allow new trades"""
        try:
            current_positions = self.position_manager.get_open_positions()
            symbol_positions = [p for p in current_positions if p['symbol'] == symbol]
            
            result = {
                'passed': len(symbol_positions) < self.trading_logic.max_positions_per_symbol,
                'current_positions': len(symbol_positions),
                'max_allowed': self.trading_logic.max_positions_per_symbol
            }
            self.logger.debug(f"Position limits check result: {result}")
            return result
        except Exception as e:
            self.logger.error(f"Error checking position limits: {str(e)}")
            return {'passed': False, 'error': str(e)}
        
    def _check_risk_reward_ratio(self, signals: list) -> dict:
        """Validate risk/reward ratios for signals"""
        try:
            for signal in signals:
                if not all([signal.entry_price, signal.stop_loss, signal.take_profit]):
                    continue
                    
                risk = abs(signal.entry_price - signal.stop_loss)
                reward = abs(signal.take_profit - signal.entry_price)
                if risk == 0:
                    continue
                    
                ratio = reward / risk
                if ratio >= self.trading_logic.min_risk_reward:
                    result = {
                        'passed': True,
                        'ratio': ratio,
                        'minimum_required': self.trading_logic.min_risk_reward
                    }
                    self.logger.debug(f"Risk/Reward check passed: {result}")
                    return result
            
            result = {
                'passed': False,
                'ratio': 0.0,
                'minimum_required': self.trading_logic.min_risk_reward
            }
            self.logger.debug(f"Risk/Reward check failed: {result}")
            return result
        except Exception as e:
            self.logger.error(f"Error checking risk/reward ratio: {str(e)}")
            return {'passed': False, 'error': str(e)}
        
    def _determine_final_status(
        self,
        consensus_strength: float,
        position_check: dict,
        risk_reward_check: dict
    ) -> dict:
        """Determine final signal status and trading eligibility"""
        try:
            # Signal must be strong enough and meet all trading criteria
            trading_eligible = (
                consensus_strength >= self.trading_logic.required_signal_strength and
                position_check['passed'] and
                risk_reward_check['passed']
            )
            
            # Determine status based on consensus strength and trading eligibility
            if trading_eligible and consensus_strength >= 0.8:
                status = 'STRONG'
            elif trading_eligible and consensus_strength >= 0.6:
                status = 'MODERATE'
            else:
                status = 'WEAK'
                
            result = {
                'trading_eligible': trading_eligible,
                'status': status
            }
            self.logger.info(f"Final status determination: {result}")
            return result
        except Exception as e:
            self.logger.error(f"Error determining final status: {str(e)}")
            return {'trading_eligible': False, 'status': 'WEAK'}