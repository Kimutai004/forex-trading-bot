from typing import List, Dict, Tuple, Optional
import MetaTrader5 as mt5
from datetime import datetime
import json
from zoneinfo import ZoneInfo

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
    
    def get_position_details(self) -> List[Dict]:
        """Get detailed position information including all timestamps and history"""
        try:
            self.logger.info(f"""
            =================== POSITION DETAILS START ===================
            Current Time (Local): {datetime.now()}
            Current Time (UTC): {datetime.now(ZoneInfo('UTC'))}
            MT5 Connected: {self.mt5_instance.connected}
            """)

            # Get current positions
            positions = mt5.positions_get()
            if positions is None:
                error = mt5.last_error()
                self.logger.error(f"Failed to get positions: {error}")
                return []

            detailed_positions = []
            for pos in positions:
                pos_dict = pos._asdict()
                
                # Get raw position data
                self.logger.info(f"""
                Raw Position Data:
                Ticket: {pos_dict.get('ticket')}
                Time: {pos_dict.get('time')}
                Time Setup: {pos_dict.get('time_setup')}
                Time Update: {pos_dict.get('time_update', 'N/A')}
                Raw Timestamp: {pos_dict.get('time')}
                """)

                # Get position history
                history = mt5.history_orders_get(
                    ticket=pos_dict.get('ticket')
                )
                if history:
                    for hist in history:
                        hist_dict = hist._asdict()
                        self.logger.info(f"""
                        Position History Entry:
                        Order Ticket: {hist_dict.get('ticket')}
                        Setup Time: {hist_dict.get('time_setup')}
                        Done Time: {hist_dict.get('time_done')}
                        State: {hist_dict.get('state')}
                        Type: {hist_dict.get('type')}
                        """)

                # Get deal history
                deals = mt5.history_deals_get(
                    ticket=pos_dict.get('ticket')
                )
                if deals:
                    for deal in deals:
                        deal_dict = deal._asdict()
                        self.logger.info(f"""
                        Deal History Entry:
                        Deal Ticket: {deal_dict.get('ticket')}
                        Order Ticket: {deal_dict.get('order')}
                        Time: {deal_dict.get('time')}
                        Type: {deal_dict.get('type')}
                        Entry: {deal_dict.get('entry')}
                        """)

                # Calculate all relevant times
                position_time = pos_dict.get('time', 0)
                server_time = datetime.fromtimestamp(position_time)
                local_time = datetime.fromtimestamp(position_time - 7200)  # Convert from EET to local
                
                self.logger.info(f"""
                Position Time Analysis:
                Position: {pos_dict.get('ticket')}
                Symbol: {pos_dict.get('symbol')}
                Type: {'BUY' if pos_dict.get('type') == 0 else 'SELL'}
                
                Timestamps:
                Raw Server Time: {position_time}
                Server Time (EET): {server_time}
                Local Time: {local_time}
                Current Time: {datetime.now()}
                
                Duration Calculation:
                Seconds Since Open: {(datetime.now() - local_time).total_seconds()}
                Minutes Since Open: {(datetime.now() - local_time).total_seconds() / 60}
                
                Position State:
                Open Price: {pos_dict.get('price_open')}
                Current Price: {pos_dict.get('price_current')}
                SL: {pos_dict.get('sl')}
                TP: {pos_dict.get('tp')}
                Profit: {pos_dict.get('profit')}
                Volume: {pos_dict.get('volume')}
                """)

                detailed_positions.append({
                    'ticket': pos_dict.get('ticket'),
                    'symbol': pos_dict.get('symbol'),
                    'type': pos_dict.get('type'),
                    'volume': pos_dict.get('volume'),
                    'time_raw': position_time,
                    'time_server': server_time,
                    'time_local': local_time,
                    'price_open': pos_dict.get('price_open'),
                    'price_current': pos_dict.get('price_current'),
                    'profit': pos_dict.get('profit'),
                    'sl': pos_dict.get('sl'),
                    'tp': pos_dict.get('tp'),
                    'raw_data': pos_dict
                })

            self.logger.info(f"""
            Position Summary:
            Total Positions: {len(detailed_positions)}
            =================== POSITION DETAILS END ===================
            """)

            return detailed_positions

        except Exception as e:
            self.logger.error(f"Error getting position details: {str(e)}")
            return []

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