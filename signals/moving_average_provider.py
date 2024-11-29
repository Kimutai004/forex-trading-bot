from datetime import datetime
from typing import List, Dict
from .signal_provider import SignalProvider, Signal, SignalType

class MovingAverageProvider(SignalProvider):
    """Simple Moving Average crossover signal provider"""
    
    def __init__(self, name: str, symbols: List[str], timeframe: str):
        """
        Initialize Moving Average signal provider
        
        Args:
            name: Provider name
            symbols: List of symbols to monitor
            timeframe: Timeframe to analyze
        """
        super().__init__(name, symbols, timeframe)
        self._parameters = {
            'fast_period': 10,
            'slow_period': 20
        }
    
    def calculate_signal(self, symbol: str, candles: List[Dict]) -> Signal:
        """
        Calculate signal based on moving average crossover
        
        Args:
            symbol: Trading symbol
            candles: List of OHLCV candles
            
        Returns:
            Signal based on MA crossover
        """
        if not candles or len(candles) < self._parameters['slow_period']:
            return Signal(
                type=SignalType.NONE,
                symbol=symbol,
                timestamp=datetime.now(),
                provider=self.name,
                comment="Insufficient data"
            )

        # Calculate fast MA
        fast_ma = sum(c['close'] for c in candles[-self._parameters['fast_period']:]) / self._parameters['fast_period']
        
        # Calculate slow MA
        slow_ma = sum(c['close'] for c in candles[-self._parameters['slow_period']:]) / self._parameters['slow_period']
        
        current_price = candles[-1]['close']

        # Determine signal type
        if fast_ma > slow_ma:
            signal_type = SignalType.BUY
            stop_loss = min(c['low'] for c in candles[-5:]) - 0.0010  # 10 pips below recent low
            take_profit = current_price + (current_price - stop_loss) * 2  # 2:1 reward ratio
        elif fast_ma < slow_ma:
            signal_type = SignalType.SELL
            stop_loss = max(c['high'] for c in candles[-5:]) + 0.0010  # 10 pips above recent high
            take_profit = current_price - (stop_loss - current_price) * 2  # 2:1 reward ratio
        else:
            signal_type = SignalType.NONE
            stop_loss = take_profit = None

        # Create and validate signal
        signal = Signal(
            type=signal_type,
            symbol=symbol,
            timestamp=datetime.now(),
            provider=self.name,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            volume=0.01,  # Default small volume
            comment=f"MA{self._parameters['fast_period']}/{self._parameters['slow_period']} Crossover"
        )
        
        # Store and return if valid
        if signal.is_valid():
            self._update_last_signal(symbol, signal)
        return signal

    def validate_parameters(self, parameters: Dict) -> bool:
        """
        Validate strategy parameters
        
        Args:
            parameters: Dictionary with fast_period and slow_period
            
        Returns:
            True if parameters are valid
        """
        if not all(key in parameters for key in ['fast_period', 'slow_period']):
            return False
            
        if not all(isinstance(val, int) and val > 0 for val in parameters.values()):
            return False
            
        if parameters['fast_period'] >= parameters['slow_period']:
            return False
            
        return True

    def update_parameters(self, fast_period: int = None, slow_period: int = None) -> bool:
        """
        Update MA parameters
        
        Args:
            fast_period: Period for fast MA
            slow_period: Period for slow MA
            
        Returns:
            True if parameters were updated successfully
        """
        new_params = self._parameters.copy()
        
        if fast_period is not None:
            new_params['fast_period'] = fast_period
        if slow_period is not None:
            new_params['slow_period'] = slow_period
            
        return super().update_parameters(new_params)