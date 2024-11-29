from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional, List
from datetime import datetime
from enum import Enum

class SignalType(Enum):
    """Type of trading signal"""
    BUY = "BUY"
    SELL = "SELL"
    CLOSE = "CLOSE"
    NONE = "NONE"

@dataclass
class Signal:
    """Trading signal data structure"""
    type: SignalType
    symbol: str
    timestamp: datetime
    provider: Optional[str] = None
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    volume: Optional[float] = None
    comment: Optional[str] = None
    extra_data: Optional[Dict] = None

    def is_valid(self) -> bool:
        """Check if signal has all required fields"""
        if self.type == SignalType.NONE:
            return True
        
        if not all([self.symbol, self.timestamp]):
            return False
            
        if self.type in [SignalType.BUY, SignalType.SELL]:
            return all([
                self.entry_price is not None,
                self.stop_loss is not None,
                self.take_profit is not None,
                self.volume is not None
            ])
            
        return True

class SignalProvider(ABC):
    """Base class for all signal providers/strategies"""
    
    def __init__(self, name: str, symbols: List[str], timeframe: str):
        """
        Initialize signal provider
        
        Args:
            name: Provider/strategy name
            symbols: List of symbols to monitor
            timeframe: Timeframe to analyze (e.g., "1H", "4H", "1D")
        """
        self.name = name
        self.symbols = symbols
        self.timeframe = timeframe
        self.is_active = True
        self._last_signal: Dict[str, Signal] = {}
        self._parameters: Dict = {}
        
    @abstractmethod
    def calculate_signal(self, symbol: str, candles: List[Dict]) -> Signal:
        """
        Calculate trading signal based on market data
        
        Args:
            symbol: Trading symbol
            candles: List of OHLCV candles with indicators
            
        Returns:
            Signal instance with trading decision
        """
        pass
    
    @abstractmethod
    def validate_parameters(self, parameters: Dict) -> bool:
        """
        Validate strategy parameters
        
        Args:
            parameters: Dictionary of parameters to validate
            
        Returns:
            True if parameters are valid
        """
        pass
    
    def update_parameters(self, parameters: Dict) -> bool:
        """
        Update strategy parameters
        
        Args:
            parameters: New parameter values
            
        Returns:
            True if parameters were updated successfully
        """
        if not self.validate_parameters(parameters):
            return False
            
        self._parameters.update(parameters)
        return True
    
    def get_parameters(self) -> Dict:
        """Get current strategy parameters"""
        return self._parameters.copy()
    
    def get_last_signal(self, symbol: str) -> Optional[Signal]:
        """
        Get last signal for symbol
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Last signal generated for symbol or None
        """
        return self._last_signal.get(symbol)
    
    def set_active(self, active: bool):
        """Enable/disable signal provider"""
        self.is_active = active
    
    def _update_last_signal(self, symbol: str, signal: Signal):
        """Update last signal for symbol"""
        self._last_signal[symbol] = signal
    
    def _validate_signal(self, signal: Signal) -> bool:
        """
        Validate signal before returning
        
        Args:
            signal: Signal to validate
            
        Returns:
            True if signal is valid
        """
        if not signal.is_valid():
            return False
            
        # Store valid signal
        self._update_last_signal(signal.symbol, signal)
        return True