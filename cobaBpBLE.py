import asyncio
from bleak import BleakScanner, BleakClient
from bleak.exc import BleakError
import struct

# UUIDs untuk Blood Pressure Service
BLOOD_PRESSURE_SERVICE_UUID = "00001810-0000-1000-8000-00805f9b34fb"
BLOOD_PRESSURE_MEASUREMENT_CHAR_UUID = "00002a35-0000-1000-8000-00805f9b34fb"

def parse_sfloat(sfloat_bytes):
    """Menguraikan format SFLOAT 16-bit. Tidak digunakan di parser ini karena nilainya integer sederhana."""
    # Format SFLOAT jarang digunakan untuk nilai tekanan darah standar mmHg.
    # Nilai-nilai ini biasanya integer sederhana. Kita akan gunakan struct.unpack.
    return struct.unpack('<h', sfloat_bytes)[0] # Asumsikan signed short 16-bit

def parse_blood_pressure_data(data: bytearray):
    """Menguraikan data dari notifikasi Blood Pressure Measurement."""
    try:
        offset = 0
        flags = data[offset]
        offset += 1
        
        # --- Interpretasi Flags ---
        units_is_kpa = (flags & 0x01) != 0
        timestamp_present = (flags & 0x02) != 0
        pulse_rate_present = (flags & 0x04) != 0
        user_id_present = (flags & 0x08) != 0
        measurement_status_present = (flags & 0x10) != 0

        unit_str = "kPa" if units_is_kpa else "mmHg"

        # --- Mengambil Nilai Tekanan Darah ---
        # Formatnya adalah SFLOAT, tapi untuk mmHg nilainya adalah integer sederhana
        # yang pas dalam 2 byte. Kita baca sebagai unsigned short little-endian.
        systolic = parse_sfloat(data[offset:offset+2])
        offset += 2
        diastolic = parse_sfloat(data[offset:offset+2])
        offset += 2
        map_pressure = parse_sfloat(data[offset:offset+2])
        offset += 2

        print("\n--- Hasil Pengukuran Tekanan Darah ---")
        print(f"Tekanan Darah: {systolic}/{diastolic} {unit_str}")
        # print(f"Mean Arterial Pressure (MAP): {map_pressure} {unit_str}")

        # # --- Mengambil Timestamp (jika ada) ---
        # if timestamp_present:
        #     # Format: year(2 bytes), month, day, hour, minute, second (masing-masing 1 byte)
        #     year, month, day, hour, minute, second = struct.unpack('<HBBBBB', data[offset:offset+7])
        #     offset += 7
        #     print(f"Waktu Pengukuran: {year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}")

        # --- Mengambil Denyut Nadi (jika ada) ---
        if pulse_rate_present:
            pulse_rate = parse_sfloat(data[offset:offset+2])
            offset += 2
            print(f"Denyut Nadi: {pulse_rate} bpm")

        # # --- Mengambil User ID (jika ada) ---
        # if user_id_present:
        #     user_id = data[offset]
        #     offset += 1
        #     print(f"User ID: {user_id}")
        
        # --- Mengambil Status Pengukuran (jika ada) ---
        if measurement_status_present:
            # Di sini bisa ditambahkan logika untuk menguraikan status (misal: body movement, cuff fit)
            # Untuk sekarang, kita hanya tampilkan nilai mentahnya.
            status_flags = struct.unpack('<H', data[offset:offset+2])[0]
            print(f"Status Pengukuran (Flags): {status_flags}")
        
        print("--------------------------------------")

    except Exception as e:
        print(f"Error saat menguraikan data: {e}")
        print(f"Data mentah yang diterima (HEX): {data.hex().upper()}")

def notification_handler(sender_handle: int, data: bytearray):
    """Fungsi yang dipanggil setiap kali notifikasi diterima."""
    parse_blood_pressure_data(data)

async def main():
    """Fungsi utama untuk scan, koneksi, dan menerima data."""
    print("Mencari perangkat tensimeter Yuwell (Blood Pressure Service)...")
    
    device = None
    try:
        # Mencari perangkat yang mengiklankan Blood Pressure Service
        device = await BleakScanner.find_device_by_filter(
            lambda d, ad: BLOOD_PRESSURE_SERVICE_UUID.lower() in ad.service_uuids,
            timeout=20.0
        )
    except BleakError as e:
        print(f"Error saat memindai: {e}")
        print("Pastikan Bluetooth di PC Anda aktif dan berfungsi.")
        return

    if not device:
        print("Tensimeter Yuwell tidak ditemukan.")
        print("Pastikan perangkat aktif dan dalam mode pairing/siap dihubungkan.")
        return

    print(f"Menghubungkan ke {device.name or 'Yuwell Tensimeter'} ({device.address})")

    async with BleakClient(device) as client:
        if not client.is_connected:
            print(f"Gagal terhubung ke {device.address}")
            return

        print("Berhasil terhubung. Mengaktifkan notifikasi...")
        try:
            await client.start_notify(BLOOD_PRESSURE_MEASUREMENT_CHAR_UUID, notification_handler)
            print("Notifikasi aktif. Menunggu data dari tensimeter...")
            print("Lakukan pengukuran pada tensimeter sekarang.")
            print("Tekan Ctrl+C untuk berhenti.")
            
            # Tetap berjalan untuk menerima data
            while client.is_connected:
                await asyncio.sleep(1)

        except BleakError as e:
            print(f"Error BLE: {e}")
        except Exception as e:
            print(f"Error tak terduga: {e}")
        finally:
            if client.is_connected:
                await client.stop_notify(BLOOD_PRESSURE_MEASUREMENT_CHAR_UUID)
            print("Program dihentikan.")

if __name__ == "__main__":
    print("--- Program Python Pembaca Tensimeter BLE ---")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram dihentikan oleh pengguna.")
    except Exception as e:
        print(f"Terjadi error pada level utama: {e}")