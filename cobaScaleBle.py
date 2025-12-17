import asyncio
from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError

# !!! DATA PENGGUNA (WAJIB DIISI) !!!
# Ganti nilai-nilai ini sesuai dengan data pengguna yang akan menggunakan timbangan
USER_HEIGHT_CM = 170.0  # Tinggi badan dalam sentimeter (cm)
USER_AGE_YEARS = 28     # Usia dalam tahun
USER_IS_MALE = True     # True jika laki-laki, False jika perempuan
last_scale_data_hex = ""

# Alamat MAC Timbangan MIBFS (ganti jika berbeda)
TARGET_SCALE_ADDRESS = "d8:e7:2f:0a:94:44" # Alamat dari contoh awalmu

# UUIDs
BODY_COMPOSITION_SERVICE_UUID = "0000181b-0000-1000-8000-00805f9b34fb"
BODY_COMPOSITION_MEASUREMENT_CHAR_UUID = "00002a9c-0000-1000-8000-00805f9b34fb"

def calculate_and_display_metrics(weight_kg):
    print("\n--- Metrik Tubuh Terhitung ---")
    print(f"Berat Badan: {weight_kg:.2f} kg")
    print("-----------------------------")

def parse_body_composition_data_python(data: bytearray):
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

            if parsed_weight_kg > 0:
                # Panggil fungsi untuk menghitung dan menampilkan semua metrik
                calculate_and_display_metrics(
                    parsed_weight_kg, 
                )
                # BARIS BARU: Setelah berhasil mencetak, simpan data ini sebagai data terakhir.
                last_scale_data_hex = current_data_hex

# def parse_body_composition_data_python(data: bytearray):
#     """Mem-parsing data dari timbangan Xiaomi/Huami."""
#     length = len(data)
#     # print(f"Menerima data (panjang {length}): {data.hex().upper()}") # Untuk debugging data mentah

#     parsed_weight_kg = -1.0
#     parsed_impedance = 0 # 0 atau 0xFFFF sering berarti tidak ada/error

#     if length == 13:
#         ctrl_byte = data[0]
#         is_stabilized = (ctrl_byte & 0x02) != 0
#         is_catty_unit = (ctrl_byte & 0x01) != 0
#         is_lbs_unit = False
        
#         if not is_catty_unit:
#             if (ctrl_byte & 0x10) != 0: # Bit 4 untuk Lbs
#                 is_lbs_unit = True
#             elif ctrl_byte == 0x12 or ctrl_byte == 0x03: # Nilai ctrl_byte spesifik untuk Lbs stabil
#                 is_lbs_unit = True
        
#         # Debugging control byte (opsional)
#         # print(f"  Ctrl Byte: 0x{ctrl_byte:02X} -> Stabil: {is_stabilized}, Catty: {is_catty_unit}, Lbs: {is_lbs_unit}")

#         if is_stabilized:
#             # Berat: byte terakhir MSB, byte kedua terakhir LSB
#             raw_weight = int.from_bytes(data[length-2:length], byteorder='little')
            
#             temp_weight = 0.0
#             if is_catty_unit:
#                 temp_weight = raw_weight / 100.0 
#                 if temp_weight > 0: parsed_weight_kg = temp_weight * 0.5 # Konversi Jin ke kg
#             elif is_lbs_unit:
#                 temp_weight = raw_weight / 100.0
#                 if temp_weight > 0: parsed_weight_kg = temp_weight * 0.453592 # Konversi lbs ke kg
#             else: # Kilogram
#                 temp_weight = raw_weight / 200.0
#                 if temp_weight > 0: parsed_weight_kg = temp_weight
            
#             # Impedansi: data[8] LSB, data[9] MSB
#             if not is_catty_unit and length >= 10: # Impedansi biasanya tidak dengan unit Catty
#                 raw_impedance = int.from_bytes(data[8:10], byteorder='little')
#                 if 0 < raw_impedance < 0xFFFE: # Filter umum nilai tidak valid
#                     parsed_impedance = raw_impedance
            
#             if parsed_weight_kg > 0:
#                 calculate_and_display_metrics(
#                     parsed_weight_kg, 
#                     parsed_impedance, 
#                     USER_HEIGHT_CM, 
#                     USER_AGE_YEARS, 
#                     USER_IS_MALE
#                 )
#             else:
#                 print("  Berat badan tidak valid dari paket Xiaomi.")
#         # else:
#             # print("  Pengukuran belum stabil (berdasarkan Control Byte Xiaomi).") # Output minimal
#     # else:
#         # print(f"  Paket data dengan panjang {length} byte tidak dikenali sebagai format berat Xiaomi.")


def notification_handler(sender_handle: int, data: bytearray):
    """Dipanggil ketika notifikasi diterima."""
    # print(f"Notifikasi dari handle {sender_handle}: {data.hex().upper()}") # Debugging data mentah
    parse_body_composition_data_python(data)


async def main_logic(target_address: str):
    print(f"Mencari perangkat dengan alamat: {target_address}...")
    device = await BleakScanner.find_device_by_address(target_address, timeout=20.0)

    if not device:
        print(f"Timbangan dengan alamat {target_address} tidak ditemukan.")
        print("Pastikan timbangan aktif dan dalam jangkauan Bluetooth.")
        return

    print(f"Terhubung ke {device.name if device.name else 'Perangkat Tanpa Nama'} ({device.address})")

    async with BleakClient(device, timeout=30.0) as client:
        if client.is_connected:
            print("Berhasil terhubung ke timbangan.")
            try:
                await client.start_notify(BODY_COMPOSITION_MEASUREMENT_CHAR_UUID, notification_handler)
                print(f"Berhasil subscribe notifikasi dari characteristic {BODY_COMPOSITION_MEASUREMENT_CHAR_UUID}")
                print("Letakkan beban pada timbangan untuk mendapatkan data...")
                print("Tekan Ctrl+C untuk berhenti.")
                
                # Tetap berjalan untuk menerima notifikasi
                # Kamu bisa mengganti ini dengan loop yang lebih canggih jika perlu
                while True:
                    await asyncio.sleep(1) # Cek koneksi atau handle aktivitas lain
                    if not client.is_connected:
                        print("Koneksi terputus.")
                        break
            except BleakError as e:
                print(f"Error saat subscribe notifikasi atau komunikasi: {e}")
            except Exception as e:
                print(f"Error tak terduga: {e}")
            finally:
                if client.is_connected:
                    print("Menghentikan notifikasi...")
                    try:
                        await client.stop_notify(BODY_COMPOSITION_MEASUREMENT_CHAR_UUID)
                    except BleakError as e:
                        print(f"Error saat menghentikan notifikasi: {e}")
                print("Selesai.")
        else:
            print("Gagal terhubung ke timbangan.")


async def scan_and_select_device():
    print("Memindai perangkat BLE selama 10 detik...")
    try:
        devices = await BleakScanner.discover(timeout=10.0)
    except BleakError as e:
        print(f"Error saat memindai: {e}")
        print("Pastikan Bluetooth di PC Anda aktif dan berfungsi.")
        return None
        
    if not devices:
        print("Tidak ada perangkat BLE yang ditemukan.")
        return None

    print("Perangkat yang ditemukan:")
    relevant_devices = []
    for i, d in enumerate(devices):
        # Filter sederhana berdasarkan nama atau jika ada service data yang relevan
        # Untuk MIBFS, nama mungkin tidak selalu ada atau konsisten
        # Kamu bisa mencoba mencari berdasarkan service UUID jika diiklankan,
        # namun MIBFS biasanya tidak mengiklankan service UUID utama secara luas
        print(f"  {i}: {d.name} ({d.address}) RSSI: {d.rssi}")
        # Untuk MIBFS, kita mungkin harus mengandalkan alamat MAC atau mencoba menghubungkan
        # ke perangkat yang "terlihat" seperti timbangan.
        # Untuk penyederhanaan, kita akan minta pengguna memilih berdasarkan alamat jika TARGET_SCALE_ADDRESS kosong.
        relevant_devices.append(d) # Untuk contoh ini, tampilkan semua

    if not relevant_devices:
        print("Tidak ada perangkat relevan yang ditemukan (coba filter lebih baik jika perlu).")
        return None

    while True:
        try:
            choice = int(input("Pilih nomor perangkat untuk dihubungkan (atau Ctrl+C untuk keluar): "))
            if 0 <= choice < len(relevant_devices):
                return relevant_devices[choice].address
            else:
                print("Pilihan tidak valid.")
        except ValueError:
            print("Masukkan nomor yang valid.")
        except KeyboardInterrupt:
            return None


if __name__ == "__main__":
    print("Program Python untuk Timbangan BLE MIBFS")
    print("Pastikan Bluetooth PC aktif.")
    print("--------------------------------------")

    address_to_connect = TARGET_SCALE_ADDRESS

    if not address_to_connect: # Jika TARGET_SCALE_ADDRESS kosong
        print("Alamat MAC target belum diatur. Mencoba memindai...")
        # Loop untuk mencoba scan sampai perangkat dipilih atau pengguna keluar
        while True:
            selected_address = asyncio.run(scan_and_select_device())
            if selected_address:
                address_to_connect = selected_address
                print(f"Akan mencoba menghubungkan ke: {address_to_connect}")
                break
            else:
                print("Tidak ada perangkat dipilih atau scan gagal.")
                retry_scan = input("Coba pindai lagi? (y/n): ").lower()
                if retry_scan != 'y':
                    print("Keluar.")
                    exit() # Keluar dari program jika tidak mau scan lagi
    
    if address_to_connect:
        try:
            asyncio.run(main_logic(address_to_connect))
        except KeyboardInterrupt:
            print("\nProgram dihentikan oleh pengguna.")
        except BleakError as e:
            print(f"Terjadi BleakError pada level utama: {e}")
            print("Pastikan Bluetooth aktif dan perangkat dalam jangkauan.")
    else:
        print("Tidak ada alamat target untuk dihubungkan. Program berakhir.")