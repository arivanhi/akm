import asyncio
import struct
from bleak import BleakClient, BleakScanner
from Crypto.Cipher import AES
import os

# === KONFIGURASI ===
SCALE_MAC = "D4:43:8A:C7:1D:9D"
BLE_KEY_HEX = "ec63e7af1b30cd188987e2d0facb09a6"
BIND_KEY = bytes.fromhex(BLE_KEY_HEX)

# UUIDs
UUID_XIAOMI_SERVICE = "0000fe95-0000-1000-8000-00805f9b34fb"
UUID_AUTH_INIT      = "00000010-0000-1000-8000-00805f9b34fb" # Write (Start Auth)
UUID_AUTH_DATA      = "00000001-0000-1000-8000-00805f9b34fb" # Notify (Challenge) & Write (Response) - Cek UUID S400 spesifik, kadang beda
# S400 mungkin pakai UUID standar 0010 untuk init dan lainnya untuk data.

async def main():
    print(f"Mencoba KONEKSI PAKSA ke {SCALE_MAC}...")
    device = await BleakScanner.find_device_by_address(SCALE_MAC, timeout=20)
    
    if not device:
        print("Perangkat tidak ditemukan.")
        return

    async with BleakClient(device) as client:
        print(f"Terhubung: {client.is_connected}")
        
        # S400 Auth Procedure (Simplified)
        # Ini eksperimental karena UUID auth S400 jarang didokumentasikan
        try:
            # 1. Coba subscribe ke semua notifikasi dulu
            for service in client.services:
                if "fe95" in str(service.uuid):
                    print("Service Xiaomi FE95 ditemukan.")
                    for char in service.characteristics:
                        if "notify" in char.properties:
                            try:
                                await client.start_notify(char.uuid, lambda s, d: print(f"Data [{char.uuid}]: {d.hex().upper()}"))
                                print(f"Subscribed ke {char.uuid}")
                            except:
                                pass
            
            print("Menunggu data (Naik ke timbangan)...")
            await asyncio.sleep(15) # Tunggu 15 detik
            
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())