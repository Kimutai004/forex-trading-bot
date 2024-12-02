from typing import List, Dict, Tuple, Optional
import MetaTrader5 as mt5
from datetime import datetime
import json

class PositionManager:
    
    def __init__(self, mt5_instance):
        """
        Initialize Position Manager
        
        Args:
            mt5_instance: Instance of MT5Trader class
        """
        self.mt5_instance = mt5_instance
        self._setup_logging()
        
    def _setup_logging(self):
        """Setup logging for position manager"""
        from src.utils.logger import setup_logger
        self.logger = setup_logger('PositionManager')

    def get_open_positions(self) -> List[Dict]:
        """Get all open positions with formatted information"""
        self.logger.info(f"""
        ================ POSITION CHECK START ================
        Time: {datetime.now()}
        MT5 Connected: {self.mt5_instance.connected}
        """)
        
        if not self.mt5_instance.connected:
            self.logger.warning("MT5 not connected - cannot get positions")
            return []

        positions = mt5.positions_get()
        if positions is None:
            error = mt5.last_error()
            self.logger.error(f"Failed to get positions: {error}")
            return []

        self.logger.info(f"Retrieved {len(positions) if positions else 0} positions from MT5")

        formatted_positions = []
        for position in positions:
            current_price = self._get_current_price(position.symbol, position.type)
            profit = position.profit
            pips = self._calculate_pips(position.symbol, position.price_open, current_price)

            # Detailed position timestamp logging
            raw_timestamp = position.time
            server_time = datetime.fromtimestamp(raw_timestamp)
            utc_time = datetime.fromtimestamp(raw_timestamp - 7200)  # Convert EET to UTC

            self.logger.info(f"""
            Position Details:
            - Ticket: {position.ticket}
            - Symbol: {position.symbol}
            - Type: {'BUY' if position.type == 0 else 'SELL'}
            - Volume: {position.volume}
            - Open Price: {position.price_open}
            - Current Price: {current_price}
            - Profit: {profit}
            - Pips: {pips}
            
            Time Information:
            - Raw Server Timestamp: {raw_timestamp}
            - Server Time (EET): {server_time}
            - UTC Time: {utc_time}
            - Current Time: {datetime.now()}
            """)

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
                'time': raw_timestamp,  # Keep raw timestamp
                'time_raw': raw_timestamp,  # Store original timestamp
                'server_time': server_time.strftime('%Y-%m-%d %H:%M:%S'),
                'utc_time': utc_time.strftime('%Y-%m-%d %H:%M:%S'),
                'timezone': 'UTC'
            })

        self.logger.info(f"""
        ================ POSITION CHECK END ================
        Total Positions: {len(formatted_positions)}
        Position Times:
        {json.dumps([{
            'ticket': p['ticket'],
            'server_time': p['server_time'],
            'utc_time': p['utc_time']
        } for p in formatted_positions], indent=2)}
        Current Time: {datetime.now()}
        """)

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
        try:
            if not self.mt5_instance.market_is_open:
                return False, "Market is closed"
                
            return self.mt5_instance.close_trade(ticket)
        except Exception as e:
            return False, f"Error closing position: {str(e)}"

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