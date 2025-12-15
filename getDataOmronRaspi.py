import asyncio
import struct
from datetime import datetime
from bleak import BleakClient, BleakScanner
from bleak.exc import BleakDBusError, BleakError

# MAC Address Tensimeter
ADDRESS = "00:5F:BF:BD:D0:D8"
UUID_BP_MEASUREMENT = "00002a35-0000-1000-8000-00805f9b34fb"

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
            print(".", end="", flush=True)
        except Exception:
            pass

async def run_cycle():
    global last_processed_time
    monitor = OmronMonitor()
    
    print(f"\n[RPi] Menunggu Omron ({ADDRESS})...")

    # 1. Scanning
    # Timeout dipersingkat agar tidak bengong terlalu lama
    device = await BleakScanner.find_device_by_address(ADDRESS, timeout=10.0)
    if not device: return 

    print(f"[DETECTED] Sinyal ditemukan. Jeda 2 detik...")
    # PENTING: Beri waktu chip Bluetooth RPi "bernapas" sebelum connect
    await asyncio.sleep(2.0)

    # 2. Connecting dengan Retry Logic Khusus RPi
    print("[CONNECTING] Mencoba masuk...")
    
    try:
        # timeout=20.0 memberi waktu RPi yang lambat untuk negosiasi MTU
        async with BleakClient(device.address, timeout=20.0, services=None) as client:
            
            # Cek pairing, tapi jangan paksa error jika gagal
            try:
                if not client.is_paired:
                    print(" (Info: Belum paired di level Bleak, mencoba pair...)")
                    await client.pair()
            except: pass # Abaikan error pairing di sini, asumsi sudah trust di OS

            print("[SUBSCRIBING] Mengambil data...")
            await client.start_notify(UUID_BP_MEASUREMENT, monitor.notification_handler)
            
            # Tunggu data
            for _ in range(8):
                if monitor.temp_measurements: 
                    print("!", end="", flush=True)
                else:
                    print(".", end="", flush=True)
                await asyncio.sleep(1)
            
            await client.stop_notify(UUID_BP_MEASUREMENT)
            print("\n[DONE] Selesai.")

    except BleakDBusError as e:
        # Menangani error "Operation already in progress"
        if "Operation already in progress" in str(e):
            print(f"\n[BUSY] Bluetooth RPi sibuk. Resetting adapter internal...")
            # Kita biarkan loop berikutnya yang menangani, tapi beri jeda panjang
            await asyncio.sleep(5)
        else:
            print(f"\n[DBUS ERROR] {e}")

    except BleakError as e:
        if "services" in str(e):
            print(f"\n[WEAK SIGNAL] Gagal baca services (Interferensi?).")
        elif "disconnected" in str(e):
             print(f"\n[DISCONNECTED] Putus tiba-tiba.")
        else:
            print(f"\n[BLEAK ERROR] {e}")
            
    except Exception as e:
        print(f"\n[ERROR UMUM] {e}")

    # 3. Processing Data
    if monitor.temp_measurements:
        latest = sorted(monitor.temp_measurements, key=lambda x: x['datetime'])[-1]
        
        if last_processed_time != latest['datetime']:
            print("\n" + "="*45)
            print("           DATA BARU (RASPBERRY PI)")
            print("="*45)
            print(f" WAKTU      : {latest['datetime'].strftime('%d-%m-%Y %H:%M:%S')}")
            print(f" TENSI      : {latest['sys']} / {latest['dia']} {latest['unit']}")
            print(f" DETAK      : {latest['pulse']} bpm")
            print("="*45)
            last_processed_time = latest['datetime']
        else:
            print("\n[INFO] Data duplikat.")
    
    print("[COOLDOWN] 5 detik...")
    await asyncio.sleep(5)

async def main():
    print("--- OMRON RPI STABILIZER ---")
    while True:
        try:
            await run_cycle()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Crash Loop: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())