from typing import List, Dict, Tuple, Optional
import MetaTrader5 as mt5
from datetime import datetime

class PositionManager:
    def __init__(self, mt5_instance):
        """
        Initialize Position Manager
        
        Args:
            mt5_instance: Instance of MT5Trader class
        """
        self.mt5_instance = mt5_instance

    def get_open_positions(self) -> List[Dict]:
        """Get all open positions with formatted information"""
        if not self.mt5_instance.connected:
            return []

        positions = mt5.positions_get()
        if positions is None:
            return []

        formatted_positions = []
        for position in positions:
            current_price = self._get_current_price(position.symbol, position.type)
            profit = position.profit
            pips = self._calculate_pips(position.symbol, position.price_open, current_price)

            formatted_positions.append({
                'ticket': position.ticket,
                'symbol': position.symbol,
                'type': 'BUY' if position.type == 0 else 'SELL',
                'volume': position.volume,
                'open_price': position.price_open,
                'current_price': current_price,
                'sl': position.sl,
                'tp': position.tp,
                'profit': profit,
                'pips': pips,
                'comment': position.comment,
                'time': datetime.fromtimestamp(position.time).strftime('%Y-%m-%d %H:%M:%S')
            })

        return formatted_positions

    def _get_current_price(self, symbol: str, position_type: int) -> float:
        """Get current bid/ask price based on position type"""
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return 0.0
        return tick.ask if position_type == 1 else tick.bid

    def _calculate_pips(self, symbol: str, open_price: float, current_price: float) -> float:
        """Calculate profit/loss in pips"""
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return 0.0
        
        digits = symbol_info.digits
        multiplier = 1 if digits == 3 or digits == 5 else 100
        
        return ((current_price - open_price) * multiplier) if digits == 3 or digits == 5 else \
               ((current_price - open_price) * multiplier)

    def close_position(self, ticket: int) -> Tuple[bool, str]:
        """Close specific position by ticket"""
        return self.mt5_instance.close_trade(ticket)

    def close_all_positions(self) -> List[Tuple[int, bool, str]]:
        """Close all open positions"""
        results = []
        positions = self.get_open_positions()
        
        for position in positions:
            success, message = self.close_position(position['ticket'])
            results.append((position['ticket'], success, message))
        
        return results

    def modify_position(
        self,
        ticket: int,
        sl: Optional[float] = None,
        tp: Optional[float] = None
    ) -> Tuple[bool, str]:
        """Modify position's SL/TP"""
        return self.mt5_instance.modify_trade(ticket, stop_loss=sl, take_profit=tp)

    def get_position_summary(self) -> Dict:
        """Get summary of all open positions"""
        positions = self.get_open_positions()
        
        return {
            'total_positions': len(positions),
            'total_profit': sum(pos['profit'] for pos in positions),
            'buy_positions': len([pos for pos in positions if pos['type'] == 'BUY']),
            'sell_positions': len([pos for pos in positions if pos['type'] == 'SELL']),
            'symbols': list(set(pos['symbol'] for pos in positions)),
            'total_volume': sum(pos['volume'] for pos in positions)
        }