from typing import Dict, List, Optional, Set
from datetime import datetime
import logging
from .base import SignalProvider, Signal, SignalType
from .evaluator import SignalEvaluator


class SignalManager:
    """Manages and coordinates multiple signal providers"""
    
    def __init__(self, mt5_trader, config_manager, trading_logic=None):
        """
        Initialize Signal Manager
        
        Args:
            mt5_trader: MT5Trader instance for market data
            config_manager: ConfigManager instance for settings
            trading_logic: Optional TradingLogic instance
        """
        self.mt5_trader = mt5_trader
        self.config_manager = config_manager
        self.trading_logic = trading_logic
        self.providers: Dict[str, SignalProvider] = {}
        self.active_symbols: Set[str] = set()
        self._setup_logging()
        self._initialize_default_providers()
        self._signal_cache = {}
        self._last_evaluation_time = {}
        
        # Only initialize signal evaluator if trading_logic is provided
        self.signal_evaluator = None
        if trading_logic:
            self.signal_evaluator = SignalEvaluator(self, trading_logic)

        
    def _setup_logging(self):
        """Setup logging for signal manager"""
        self.logger = logging.getLogger('SignalManager')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
            
    def _initialize_default_providers(self):
        """Initialize default signal providers"""
        favorite_symbols = self.config_manager.get_setting('favorite_symbols', [])
        if not favorite_symbols:
            self.logger.warning("No favorite symbols configured")
            return
            
        try:
            from .moving_average_provider import MovingAverageProvider
            
            # Add Moving Average provider
            ma_provider = MovingAverageProvider(
                name="MA Crossover",
                symbols=favorite_symbols,
                timeframe="H1"
            )
            self.add_provider(ma_provider)
            self.logger.info(f"Added default MA Crossover provider for symbols: {favorite_symbols}")
            
        except Exception as e:
            self.logger.error(f"Error initializing default providers: {str(e)}")
    
    def add_provider(self, provider: SignalProvider) -> bool:
        """
        Add new signal provider
        
        Args:
            provider: SignalProvider instance
            
        Returns:
            True if provider was added successfully
        """
        if provider.name in self.providers:
            self.logger.warning(f"Provider {provider.name} already exists")
            return False
            
        self.providers[provider.name] = provider
        self.active_symbols.update(provider.symbols)
        self.logger.info(f"Added provider: {provider.name}")
        return True
    
    def remove_provider(self, provider_name: str) -> bool:
        """
        Remove signal provider
        
        Args:
            provider_name: Name of provider to remove
            
        Returns:
            True if provider was removed successfully
        """
        if provider_name not in self.providers:
            self.logger.warning(f"Provider {provider_name} not found")
            return False
            
        provider = self.providers.pop(provider_name)
        self._update_active_symbols()
        self.logger.info(f"Removed provider: {provider_name}")
        return True
    
    def _update_active_symbols(self):
        """Update set of active symbols from all providers"""
        self.active_symbols = set()
        for provider in self.providers.values():
            if provider.is_active:
                self.active_symbols.update(provider.symbols)
    
    def get_signals(self, symbol: str) -> List[Signal]:
        """Get signals from all active providers for symbol"""
        current_time = datetime.now()
        
        # Check cache first (valid for 1 minute)
        if (symbol in self._signal_cache and symbol in self._last_evaluation_time and
            (current_time - self._last_evaluation_time[symbol]).total_seconds() < 60):
            return self._signal_cache[symbol]
            
        if not self.providers:
            self.logger.warning("No signal providers configured")
            return []
            
        if symbol not in self.active_symbols:
            self.logger.warning(f"No active providers for symbol {symbol}")
            return []
            
        signals = []
        
        # Get market data
        candles = self._get_market_data(symbol)
        if not candles:
            self.logger.warning(f"No market data available for {symbol}")
            return signals
        
        # Get signals from each active provider
        for provider in self.providers.values():
            if not provider.is_active or symbol not in provider.symbols:
                continue
                
            try:
                signal = provider.calculate_signal(symbol, candles)
                if signal and signal.is_valid():
                    signals.append(signal)
                    
            except Exception as e:
                self.logger.error(
                    f"Error getting signal from {provider.name}: {str(e)}"
                )
        
        # Only evaluate signals if we have a signal evaluator
        if signals and self.signal_evaluator:
            try:
                evaluation = self.signal_evaluator.evaluate_signal(symbol, signals)
                
                # Update signal strengths based on evaluation
                for signal in signals:
                    signal.strength = evaluation['signal_strength']
                    signal.trading_eligible = evaluation['trading_eligible']
                    signal.evaluation_details = evaluation['details']
                    
                self.logger.info(
                    f"Got signals for {symbol}: Strength={evaluation['signal_strength']:.2f}, "
                    f"Status={evaluation['status']}, Eligible={evaluation['trading_eligible']}"
                )
            except Exception as e:
                self.logger.error(f"Error evaluating signals: {str(e)}")
        
        # Update cache
        self._signal_cache[symbol] = signals
        self._last_evaluation_time[symbol] = current_time
        
        return signals
    
    def _get_market_data(self, symbol: str) -> List[Dict]:
        """
        Get market data for symbol
        
        Args:
            symbol: Trading symbol
            
        Returns:
            List of OHLCV candles with indicators
        """
        try:
            # Get data from market watcher
            candles = self.mt5_trader.market_watcher.get_ohlcv_data(
                symbol=symbol,
                timeframe="H1",  # Default timeframe
                bars=100,
                include_incomplete=False
            )
            
            if not candles:
                self.logger.warning(f"No market data available for {symbol}")
                return []
            
            # Convert MarketData objects to dictionaries
            return [
                {
                    'timestamp': candle.timestamp,
                    'open': candle.open,
                    'high': candle.high,
                    'low': candle.low,
                    'close': candle.close,
                    'volume': candle.volume,
                    'tick_volume': candle.tick_volume,
                    'spread': candle.spread
                }
                for candle in candles
            ]
            
        except Exception as e:
            self.logger.error(f"Error getting market data for {symbol}: {str(e)}")
            return []
    
    def get_consensus_signal(self, symbol: str) -> Optional[Signal]:
        """
        Get consensus signal from all providers
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Signal based on consensus or None
        """
        signals = self.get_signals(symbol)
        if not signals:
            return None
            
        # Count signal types
        signal_counts = {
            SignalType.BUY: 0,
            SignalType.SELL: 0,
            SignalType.CLOSE: 0,
            SignalType.NONE: 0
        }
        
        for signal in signals:
            signal_counts[signal.type] += 1
        
        # Get majority signal type
        total_signals = len(signals)
        consensus_threshold = self.config_manager.get_setting(
            'signal_consensus_threshold', 0.66
        )
        
        for signal_type, count in signal_counts.items():
            if count / total_signals >= consensus_threshold:
                return self._create_consensus_signal(
                    signal_type, symbol, signals
                )
        
        return None
    
    def _create_consensus_signal(
        self, 
        signal_type: SignalType,
        symbol: str,
        signals: List[Signal]
    ) -> Signal:
        """Create consensus signal from multiple signals"""
        matching_signals = [s for s in signals if s.type == signal_type]
        
        if not matching_signals:
            return Signal(
                type=SignalType.NONE,
                symbol=symbol,
                timestamp=datetime.now()
            )
        
        # Average the entry, sl, and tp prices
        if signal_type in [SignalType.BUY, SignalType.SELL]:
            entry_prices = [s.entry_price for s in matching_signals if s.entry_price]
            sl_prices = [s.stop_loss for s in matching_signals if s.stop_loss]
            tp_prices = [s.take_profit for s in matching_signals if s.take_profit]
            volumes = [s.volume for s in matching_signals if s.volume]
            
            return Signal(
                type=signal_type,
                symbol=symbol,
                timestamp=datetime.now(),
                entry_price=sum(entry_prices) / len(entry_prices) if entry_prices else None,
                stop_loss=sum(sl_prices) / len(sl_prices) if sl_prices else None,
                take_profit=sum(tp_prices) / len(tp_prices) if tp_prices else None,
                volume=sum(volumes) / len(volumes) if volumes else None,
                comment="Consensus signal"
            )
        
        return Signal(
            type=signal_type,
            symbol=symbol,
            timestamp=datetime.now(),
            comment="Consensus signal"
        )
    
    def get_active_providers(self) -> List[str]:
        """Get list of active provider names"""
        return [name for name, provider in self.providers.items() 
                if provider.is_active]
    
    def get_provider_signals(self, provider_name: str, symbol: str) -> Optional[Signal]:
        """
        Get signals from specific provider
        
        Args:
            provider_name: Name of provider
            symbol: Trading symbol
            
        Returns:
            Signal from provider or None
        """
        if provider_name not in self.providers:
            self.logger.warning(f"Provider {provider_name} not found")
            return None
            
        provider = self.providers[provider_name]
        if not provider.is_active or symbol not in provider.symbols:
            return None
            
        candles = self._get_market_data(symbol)
        if not candles:
            return None
            
        try:
            return provider.calculate_signal(symbol, candles)
        except Exception as e:
            self.logger.error(
                f"Error getting signal from {provider_name}: {str(e)}"
            )
            return None

    def show_active_signals(self) -> str:
        """Display current signals for all active symbols"""
        if not self.providers:
            return "No signal providers configured. Please add providers first."
            
        if not self.active_symbols:
            return "No active symbols configured. Please check provider configuration."
            
        symbols = self.config_manager.get_setting('favorite_symbols', [])
        signals_found = False
        output = []
        
        for symbol in symbols:
            signals = self.get_signals(symbol)
            if signals:
                signals_found = True
                evaluation = self.signal_evaluator.evaluate_signal(symbol)
                
                output.append(f"\nSignals for {symbol}:")
                output.append(f"Signal Strength: {evaluation['signal_strength']:.2f}")
                output.append(f"Status: {evaluation['status']}")
                output.append(f"Trading Eligible: {'Yes' if evaluation['trading_eligible'] else 'No'}")
                
                if not evaluation['trading_eligible'] and evaluation['details']:
                    output.append("Reason not eligible:")
                    for key, value in evaluation['details'].items():
                        if isinstance(value, dict) and 'passed' in value:
                            if not value['passed']:
                                output.append(f"- Failed {key} check")
        
        if not signals_found:
            return "No active signals at this time."
        
        return "\n".join(output)