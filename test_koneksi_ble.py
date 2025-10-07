import asyncio
from bleak import BleakScanner, BleakClient

# --- KONFIGURASI (HARUS SAMA DENGAN DI ESP32) ---
DEVICE_NAME = "AKM_ESP32"
DATA_CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"    # Untuk Menerima Data (Notify)
COMMAND_CHARACTERISTIC_UUID = "c82f254d-793d-42a9-a864-e88307223b33" # Untuk Mengirim Flag (Write)
# ----------------------------------------------------

def notification_handler(sender, data):
    """Fungsi yang dipanggil setiap kali ada data notifikasi dari ESP32."""
    print(f"Data diterima: '{data.decode()}'")

async def main():
    """Fungsi utama untuk scanning, koneksi, dan interaksi."""
    print(f"Mencari perangkat bernama '{DEVICE_NAME}'...")
    device = await BleakScanner.find_device_by_name(DEVICE_NAME)

    if not device:
        print(f"Error: Perangkat '{DEVICE_NAME}' tidak ditemukan. Pastikan ESP32 aktif dan tidak terhubung ke perangkat lain.")
        return

    print(f"Perangkat ditemukan! Mencoba terhubung ke {device.address}...")

    try:
        async with BleakClient(device) as client:
            print(f">>> Berhasil terhubung ke {DEVICE_NAME}")

            # Mulai mendengarkan notifikasi dari ESP32
            await client.start_notify(DATA_CHARACTERISTIC_UUID, notification_handler)
            print(">>> Mendengarkan data dari ESP32...")

            # Loop untuk mengirim perintah dari terminal
            loop = asyncio.get_running_loop()
            while True:
                # Dapatkan input dari user tanpa memblokir asyncio
                command = await loop.run_in_executor(
                    None, 
                    lambda: input("Ketik flag (1/2/3) atau 'exit' untuk keluar: ")
                )

                if command.lower() == 'exit':
                    break
                
                if command in ['1', '2', '3']:
                    print(f"Mengirim flag '{command}'...")
                    await client.write_gatt_char(COMMAND_CHARACTERISTIC_UUID, command.encode())
                else:
                    print("Input tidak valid. Silakan masukkan 1, 2, 3, atau exit.")
            
            # Berhenti mendengarkan notifikasi sebelum keluar
            await client.stop_notify(DATA_CHARACTERISTIC_UUID)

    except Exception as e:
        print(f"Terjadi error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram dihentikan.")