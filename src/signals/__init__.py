# src/signals/__init__.py
from .providers.manager import SignalManager
from .providers.evaluator import SignalEvaluator
from .providers.base import SignalType, Signal
from .providers.moving_average_provider import MovingAverageProvider

__all__ = [
    'SignalManager',
    'SignalEvaluator',
    'SignalType',
    'Signal',
    'MovingAverageProvider'
]