import asyncio
import struct
from datetime import datetime
from bleak import BleakClient, BleakScanner

# MAC Address Tensimeter Baru
ADDRESS = "00:5F:BF:BD:D0:D8"
UUID_BP_MEASUREMENT = "00002a35-0000-1000-8000-00805f9b34fb"

# Variabel Global
last_processed_time = None
data_received_flag = False

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
        global data_received_flag
        data_received_flag = True
        
        # Print Raw Hex agar terlihat ada kehidupan
        print(f"\n[DEBUG] RAW HEX: {data.hex()}")

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
            
            dt_object = datetime.now()
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
            print("[DEBUG] Decoding OK.")
            
        except Exception as e:
            print(f"[DEBUG] Error Decoding: {e}")

async def run_cycle():
    global last_processed_time, data_received_flag
    monitor = OmronMonitor()
    data_received_flag = False
    
    print(f"\n[STANDBY] Menunggu Omron ({ADDRESS})...")

    # 1. Scanning
    device = await BleakScanner.find_device_by_address(ADDRESS, timeout=None)
    if not device: return 

    print(f"[DETECTED] Sinyal masuk. Connecting...")

    # 2. Connecting
    try:
        async with BleakClient(device) as client:
            print(f"[CONNECTED] Terhubung ke alat.")
            
            # --- BAGIAN INI SUDAH DIPERBAIKI (SAFE VERSION) ---
            print("Mencoba meminta Pairing (Cek notifikasi Windows)...")
            try:
                # Kita coba pair paksa tanpa cek status dulu
                await client.pair()
            except Exception as e:
                # Jika error (misal sudah paired), abaikan saja
                print(f"Info Pairing: {e} (Lanjut...)")
            
            # Subscribe
            print("[SUBSCRIBING] Mendengarkan data...")
            await client.start_notify(UUID_BP_MEASUREMENT, monitor.notification_handler)
            
            # Tunggu data mengalir
            for i in range(8):
                if data_received_flag:
                    print("!", end="", flush=True)
                else:
                    print(".", end="", flush=True)
                await asyncio.sleep(1)
            
            await client.stop_notify(UUID_BP_MEASUREMENT)
            print("\n[DONE] Sesi selesai.")
            
    except Exception as e:
        print(f"\n[ERROR] Koneksi: {e}")

    # 3. Tampilkan Data
    if monitor.temp_measurements:
        latest = sorted(monitor.temp_measurements, key=lambda x: x['datetime'])[-1]
        
        # Logika anti-duplikat
        if last_processed_time != latest['datetime']:
            print("\n" + "="*45)
            print("           DATA BARU DITERIMA")
            print("="*45)
            print(f" WAKTU      : {latest['datetime'].strftime('%d-%m-%Y %H:%M:%S')}")
            print(f" TENSI      : {latest['sys']} / {latest['dia']} {latest['unit']}")
            print(f" DETAK      : {latest['pulse']} bpm")
            print("="*45)
            last_processed_time = latest['datetime']
        else:
            print("\n[INFO] Data diterima, tapi sama dengan sebelumnya (Duplikat).")
    else:
        # Jika kosong, beri saran troubleshooting
        if not data_received_flag:
            print("\n[INFO] Data KOSONG. Pastikan:")
            print("       1. Klik 'Allow/Pair' pada notifikasi Windows.")
            print("       2. Ada pengukuran BARU di memori alat.")

    print("[COOLDOWN] 5 detik...")
    await asyncio.sleep(5)

async def main():
    print("--- OMRON FIX OLD VERSION ---")
    while True:
        try:
            await run_cycle()
        except KeyboardInterrupt:
            break
        except Exception:
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())