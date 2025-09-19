import asyncio
import sys
from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError
import struct

# --- Blok untuk mendeteksi input keyboard 'q' ---
# Diperlukan untuk fitur "berhenti dengan tombol q" tanpa memblokir program
program_is_running = True
try:
    # Untuk Windows
    import msvcrt
    def kbhit():
        return msvcrt.kbhit()
    def getch():
        return msvcrt.getch().decode()
except ImportError:
    # Untuk Linux/macOS
    import termios, tty, select
    def kbhit():
        return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])
    def getch():
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

async def check_for_quit():
    """Tugas di latar belakang untuk memeriksa apakah tombol 'q' ditekan."""
    global program_is_running
    while program_is_running:
        if kbhit() and getch().lower() == 'q':
            print("\nTombol 'q' ditekan. Program akan berhenti...")
            program_is_running = False
        await asyncio.sleep(0.1)
# --- Akhir Blok Keyboard ---


# ==============================================================================
# === KONFIGURASI PERANGKAT & PENGGUNA (WAJIB DIISI) ===
# ==============================================================================

# --- Data Pengguna untuk Timbangan ---
# USER_HEIGHT_CM = 170.0  # Tinggi badan dalam sentimeter (cm)
# USER_AGE_YEARS = 30     # Usia dalam tahun
# USER_IS_MALE = True     # true jika laki-laki, false jika perempuan
last_scale_data_hex = ""
# --- Alamat MAC Perangkat ---
SCALE_ADDRESS = "d8:e7:2f:09:84:f9" # Ganti dengan MAC Address Timbangan Mi Scale/MIBFS Anda
TENSI_ADDRESS = "d0:20:43:20:01:2d"  # !!! GANTI DENGAN MAC ADDRESS YUWELL ANDA !!!

# --- UUIDs Timbangan ---
SCALE_SERVICE_UUID = "0000181b-0000-1000-8000-00805f9b34fb"
SCALE_CHAR_UUID = "00002a9c-0000-1000-8000-00805f9b34fb"

# --- UUIDs Tensimeter ---
TENSI_SERVICE_UUID = "00001810-0000-1000-8000-00805f9b34fb"
TENSI_CHAR_UUID = "00002a35-0000-1000-8000-00805f9b34fb"

# ==============================================================================
# === FUNGSI PARSING & KALKULASI (Tidak perlu diubah) ===
# ==============================================================================

def calculate_and_display_metrics(weight_kg):
    """Menghitung dan menampilkan semua metrik tubuh dari data timbangan."""
    print("\n--- [TIMBANGAN] Hasil Pengukuran Komposisi Tubuh ---")
    print(f"  Berat Badan: {weight_kg:.2f} kg")
    print("-----------------------------------------------------")

def parse_scale_data(data: bytearray):
    """Menguraikan data dari timbangan Xiaomi/Huami dan menghindari print berulang."""
    global last_scale_data_hex # BARIS BARU: Gunakan variabel global

    current_data_hex = data.hex() # BARIS BARU: Ubah data saat ini menjadi teks hex

    # BARIS BARU: Jika data yang masuk sama persis dengan yang terakhir, abaikan.
    if current_data_hex == last_scale_data_hex:
        return

    length = len(data)
    if length == 13:
        ctrl_byte = data[0]
        is_stabilized = (ctrl_byte & 0x02) != 0

        if is_stabilized:
            is_catty_unit = (ctrl_byte & 0x01) != 0
            is_lbs_unit = not is_catty_unit and ((ctrl_byte & 0x10) != 0 or ctrl_byte in [0x12, 0x03])

            raw_weight = int.from_bytes(data[11:13], byteorder='little')
            parsed_weight_kg = -1.0

            if is_catty_unit: parsed_weight_kg = (raw_weight / 100.0) * 0.5
            elif is_lbs_unit: parsed_weight_kg = (raw_weight / 100.0) * 0.453592
            else: parsed_weight_kg = raw_weight / 200.0

            # raw_impedance = int.from_bytes(data[8:10], byteorder='little') if not is_catty_unit else 0

            if parsed_weight_kg > 0:
                # Panggil fungsi untuk menghitung dan menampilkan semua metrik
                calculate_and_display_metrics(
                    parsed_weight_kg, 
                )
                # BARIS BARU: Setelah berhasil mencetak, simpan data ini sebagai data terakhir.
                last_scale_data_hex = current_data_hex

def parse_tensimeter_data(data: bytearray):
    """Menguraikan data dari notifikasi Tensimeter dengan logika offset yang benar."""
    try:
        offset = 0
        flags = data[offset]
        offset += 1 # Pindah ke byte selanjutnya setelah flags
        
        # --- Interpretasi Flags ---
        units_is_kpa = (flags & 0x01) != 0
        timestamp_present = (flags & 0x02) != 0
        pulse_rate_present = (flags & 0x04) != 0
        
        unit_str = "kPa" if units_is_kpa else "mmHg"

        systolic = int.from_bytes(data[offset:offset+2], byteorder='little')
        offset += 2
        diastolic = int.from_bytes(data[offset:offset+2], byteorder='little')
        offset += 2
        offset += 2
        
        if timestamp_present:
            offset += 7 

        # --- Mengambil Denyut Nadi dari posisi yang benar (jika ada) ---
        pulse_rate = 0
        if pulse_rate_present:
            # Sekarang 'offset' sudah menunjuk ke posisi data denyut nadi yang benar
            pulse_rate = int.from_bytes(data[offset:offset+2], byteorder='little')
            offset += 2

        # --- Menampilkan Hasil ---
        print("\n--- [TENSIMETER] Hasil Pengukuran ---")
        print(f"  Tekanan Darah: {systolic}/{diastolic} {unit_str}")
        
        if pulse_rate_present and pulse_rate > 0:
            print(f"  Denyut Nadi: {pulse_rate} bpm")
        
        print("-----------------------------------")

    except Exception as e:
        print(f"[TENSIMETER] Error saat menguraikan data: {e}")
        print(f"  Data mentah yang mungkin menyebabkan error (HEX): {data.hex().upper()}")

# ==============================================================================
# === FUNGSI UTAMA UNTUK KONEKSI DAN MONITORING ===
# ==============================================================================

async def monitor_device(device_name: str, address: str, char_uuid: str, parser_func: callable):
    """Fungsi generik untuk memonitor satu perangkat BLE dengan auto-reconnect."""
    def notification_handler(sender_handle: int, data: bytearray):
        parser_func(data)

    while program_is_running:
        try:
            print(f"Mencari {device_name} ({address})...")
            device = await BleakScanner.find_device_by_address(address, timeout=5.0)
            
            if not device:
                print(f"{device_name} tidak ditemukan. Mencoba lagi dalam 10 detik...")
                await asyncio.sleep(10)
                continue

            print(f"Menghubungkan ke {device_name}...")
            async with BleakClient(device) as client:
                if client.is_connected:
                    print(f"Terhubung ke {device_name}. Mengaktifkan notifikasi...")
                    await client.start_notify(char_uuid, notification_handler)
                    
                    # Loop untuk menjaga koneksi tetap aktif
                    while client.is_connected and program_is_running:
                        await asyncio.sleep(1)

                    # Jika loop ini berhenti, berarti koneksi terputus atau program berhenti
                    if program_is_running:
                         print(f"Koneksi ke {device_name} terputus.")
                
        except BleakError as e:
            print(f"Error BLE dengan {device_name}: {e}. Mencoba lagi...")
        except Exception as e:
            print(f"Error tak terduga dengan {device_name}: {e}. Mencoba lagi...")

        if program_is_running:
            await asyncio.sleep(5) # Jeda sebelum mencoba menghubungkan kembali
    print(f"Monitoring untuk {device_name} berhenti.")


async def main():
    """Fungsi utama untuk menjalankan semua tugas secara bersamaan."""
    print("Program Monitor Kesehatan BLE Dimulai.")
    print("Tekan tombol 'q' kapan saja untuk berhenti.")
    print("-" * 50)
    
    # Membuat dan menjalankan tugas untuk setiap perangkat dan keyboard listener
    keyboard_task = asyncio.create_task(check_for_quit())
    scale_task = asyncio.create_task(monitor_device("Timbangan", SCALE_ADDRESS, SCALE_CHAR_UUID, parse_scale_data))
    tensi_task = asyncio.create_task(monitor_device("Tensimeter", TENSI_ADDRESS, TENSI_CHAR_UUID, parse_tensimeter_data))

    await asyncio.gather(keyboard_task, scale_task, tensi_task)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram dihentikan secara paksa.")
    finally:
        print("Program Selesai.")