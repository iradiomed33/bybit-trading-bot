from dotenv import load_dotenv
load_dotenv()
from exchange.base_client import BybitRestClient
from exchange.instruments import InstrumentsManager
import os

c = BybitRestClient(os.getenv('BYBIT_API_KEY'), os.getenv('BYBIT_API_SECRET'), testnet=True)
mgr = InstrumentsManager(c)
mgr.load_instruments()

for symbol in ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT']:
    info = mgr.get_instrument(symbol)
    if info:
        print(f"\n=== {symbol} ===")
        print(f"  tickSize: {info['tickSize']}")
        print(f"  qtyStep: {info['qtyStep']}")
        print(f"  minOrderQty: {info['minOrderQty']}")
        print(f"  minNotional: {info['minNotional']}")
