#!/usr/bin/env python3
"""
Wallet Status Script - zeigt Eli's Balances auf allen Netzwerken
"""

import sys
from pathlib import Path

# Füge das eli Modul zum Python Path hinzu
sys.path.append("/app")

from eli.wallet.manager import WalletManager

def main():
    print("🔍 Eli's Wallet Status\n")
    print("=" * 50)
    
    # Base Mainnet (Haupt-Wallet)
    wallet_base = WalletManager(network="base_mainnet")
    
    if not wallet_base.is_initialized():
        print("❌ Wallet nicht initialisiert!")
        return
    
    print(f"📍 Adresse: {wallet_base.address}")
    print()
    
    # Alle Netzwerke prüfen
    all_balances = wallet_base.get_all_balances()
    
    for network, data in all_balances.items():
        if "error" in data:
            print(f"❌ {data.get('name', network)}: {data['error']}")
        else:
            print(f"🌐 {data['name']}:")
            print(f"   ETH: {data['eth']:.6f}")
            print(f"   USDC: {data['usdc']:.2f}")
            print(f"   Explorer: {data['explorer']}")
        print()
    
    print("=" * 50)

if __name__ == "__main__":
    main()