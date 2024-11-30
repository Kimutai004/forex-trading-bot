import sys
import os

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    try:
        # Core imports
        from src.core.trading.mt5 import MT5Trader
        from src.core.trading.positions import PositionManager
        from src.core.market.watcher import MarketWatcher
        from src.core.market.sessions import MarketSessionManager
        from src.core.system.monitor import BotStatusManager
        from src.core.system.menu import MenuManager
        
        # Signal imports
        from src.signals.providers.base import Signal, SignalType
        from src.signals.providers.manager import SignalManager
        from src.signals.providers.evaluator import SignalEvaluator
        from src.signals.providers.moving_average_provider import MovingAverageProvider
        
        # Utils imports
        from src.utils.logger import setup_logger
        from src.utils.trading_logger import TradingLogger
        
        print("✅ All imports successful!")
        return True
    except ImportError as e:
        print(f"❌ Import error: {str(e)}")
        return False

if __name__ == "__main__":
    print("Running system tests...")
    imports_ok = test_imports()
    
    print("\nTest Summary:")
    print(f"Imports: {'✅' if imports_ok else '❌'}")