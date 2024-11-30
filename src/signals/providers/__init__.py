# Correct imports for src/signals/providers/__init__.py
from .base import Signal, SignalType, SignalProvider
from .manager import SignalManager
from .evaluator import SignalEvaluator
from .moving_average_provider import MovingAverageProvider

__all__ = [
    'Signal',
    'SignalType',
    'SignalProvider',
    'SignalManager',
    'SignalEvaluator',
    'MovingAverageProvider'
]