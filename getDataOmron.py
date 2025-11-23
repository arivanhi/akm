import asyncio
import struct
from datetime import datetime
from bleak import BleakClient, BleakScanner

# --- KONFIGURASI ---
ADDRESS = "00:5F:BF:83:39:A8" # MAC HEM-7156T Anda
UUID_BP_MEASUREMENT = "00002a35-0000-1000-8000-00805f9b34fb"

# Menyimpan data terakhir agar tidak duplicate print
last_processed_time = None

def decode_sfloat(data):
    raw = struct.unpack('<H', data)[0]
    mantissa = raw & 0x0FFF
    exponent = (raw >> 12) & 0x0F
    if exponent >= 0x08: exponent = -((0x0F + 1) - exponent)
    if mantissa >= 0x0800: mantissa = -((0xFFF + 1) - mantissa)
    return mantissa * (10 ** exponent)

class OmronMonitor:
    def __init__(self):
        self.temp_measurements = []

    def notification_handler(self, sender, data):
        try:
            flags = data[0]
            unit = "kPa" if (flags & 0x01) else "mmHg"
            has_timestamp = (flags & 0x02)
            has_pulse = (flags & 0x04)
            
            index = 1
            systolic = decode_sfloat(data[index:index+2])
            diastolic = decode_sfloat(data[index+2:index+4])
            mean_ap = decode_sfloat(data[index+4:index+6])
            index += 6
            
            dt_object = datetime.min 
            if has_timestamp:
                year = struct.unpack('<H', data[index:index+2])[0]
                month = data[index+2]
                day = data[index+3]
                hour = data[index+4]
                minute = data[index+5]
                second = data[index+6]
                dt_object = datetime(year, month, day, hour, minute, second)
                index += 7
                
            pulse = 0
            if has_pulse:
                pulse = decode_sfloat(data[index:index+2])
                
            record = {
                "datetime": dt_object,
                "sys": int(systolic),
                "dia": int(diastolic),
                "pulse": int(pulse),
                "map": int(mean_ap),
                "unit": unit
            }
            self.temp_measurements.append(record)
            print(".", end="", flush=True)
            
        except Exception:
            pass

async def run_cycle():
    global last_processed_time
    monitor = OmronMonitor()
    
    print(f"\n[STANDBY] Menunggu sinyal dari Omron ({ADDRESS})...")
    print("          (Silakan lakukan pengukuran atau tekan tombol Sync)")

    # 1. Scanning Spesifik (Hemat daya, menunggu sampai alat menyala)
    device = await BleakScanner.find_device_by_address(ADDRESS, timeout=None)
    
    if not device:
        return # Retry loop

    print(f"[DETECTED] Sinyal ditemukan! Mencoba menghubungkan...")

    # 2. Connecting & Fetching
    try:
        async with BleakClient(device) as client:
            print("[CONNECTED] Mengunduh data", end="")
            
            # Optional: Pairing (biasanya sekali saja cukup, tapi kita keep agar robust)
            try:
                if not client.is_paired: await client.pair()
            except: pass

            await client.start_notify(UUID_BP_MEASUREMENT, monitor.notification_handler)
            
            # Beri waktu data mengalir (Omron kirim burst cepat)
            await asyncio.sleep(5) 
            
            await client.stop_notify(UUID_BP_MEASUREMENT)
            print("\n[DONE] Pengunduhan selesai.")
            
    except Exception as e:
        print(f"\n[INFO] Koneksi terputus (Normal untuk Omron): {e}")

    # 3. Processing Data Terbaru
    if monitor.temp_measurements:
        # Ambil yang paling baru berdasarkan waktu
        latest = sorted(monitor.temp_measurements, key=lambda x: x['datetime'])[-1]
        
        # Cek apakah ini data baru atau data lama yang dikirim ulang
        if last_processed_time != latest['datetime']:
            print("\n" + "="*45)
            print("           DATA PENGUKURAN BARU")
            print("="*45)
            print(f" WAKTU      : {latest['datetime'].strftime('%d-%m-%Y %H:%M:%S')}")
            print(f" TENSI      : {latest['sys']} / {latest['dia']} {latest['unit']}")
            print(f" DETAK      : {latest['pulse']} bpm")
            print("="*45)
            
            # Update tracker
            last_processed_time = latest['datetime']
        else:
            print("\n[INFO] Data sudah up-to-date (Tidak ada pengukuran baru).")
    
    # 4. Cooldown agar tidak spamming connect saat alat masih nyala
    print("[COOLDOWN] Jeda 10 detik sebelum scan ulang...")
    await asyncio.sleep(10)

async def main():
    print("--- MONITOR OMRON HEM-7156T OTOMATIS ---")
    print("Tekan Ctrl+C untuk menghentikan program.")
    
    while True:
        try:
            await run_cycle()
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Error Loop: {e}. Restarting scan...")
            await asyncio.sleep(2)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram dihentikan oleh user.")