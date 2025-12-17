import asyncio
import json
import paho.mqtt.client as mqtt
from bleak import BleakClient, BleakScanner, BleakError

# --- KONFIGURASI MQTT ---
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_CMD_TOPIC = "akm/command"          # Topik untuk menerima perintah (Flag 6)
MQTT_DATA_TOPIC = "akm/prediction_data" # Topik untuk mengirim hasil ke Server/Web

# --- KONFIGURASI TIMBANGAN (Ganti MAC Address Anda) ---
TARGET_SCALE_ADDRESS = "d8:e7:2f:0a:94:44" 
BODY_COMPOSITION_UUID = "00002a9c-0000-1000-8000-00805f9b34fb"

# --- VARIABEL GLOBAL ---
should_measure = False  # Flag untuk memulai pengukuran
last_weight = 0.0
client_mqtt = None

# ====================================================================
# 1. FUNGSI MQTT (Komunikasi dengan Node-RED/Web)
# ====================================================================
def on_connect(client, userdata, flags, rc):
    print(f"[MQTT] Terhubung ke Broker. Code: {rc}")
    client.subscribe(MQTT_CMD_TOPIC)

def on_message(client, userdata, msg):
    global should_measure
    try:
        payload = msg.payload.decode("utf-8")
        print(f"[MQTT] Perintah diterima: {payload}")
        
        # Cek jika perintahnya adalah '6' (Flag untuk Berat Badan)
        if payload.strip() == "6":
            print("[SISTEM] Memulai proses scanning timbangan...")
            should_measure = True
    except Exception as e:
        print(f"[MQTT] Error parsing message: {e}")

# ====================================================================
# 2. LOGIKA BLE (Timbangan Xiaomi)
# ====================================================================
def parse_data(data: bytearray):
    """Menerjemahkan data hex dari timbangan"""
    if len(data) < 13: return None

    ctrl_byte = data[0]
    is_stabilized = (ctrl_byte & 0x02) != 0
    is_catty = (ctrl_byte & 0x01) != 0
    is_lbs = (ctrl_byte & 0x10) != 0

    # Ambil data berat (Byte 11 & 12)
    raw_weight = int.from_bytes(data[11:13], byteorder='little')
    weight_kg = 0.0

    # Konversi satuan
    if is_catty: weight_kg = (raw_weight / 100.0) * 0.5
    elif is_lbs: weight_kg = (raw_weight / 100.0) * 0.453592
    else: weight_kg = raw_weight / 200.0 # Satuan default KG

    return {
        "weight": weight_kg,
        "is_stable": is_stabilized
    }

def notification_handler(sender, data):
    """Callback saat data masuk dari Bluetooth"""
    global should_measure, last_weight, client_mqtt
    
    result = parse_data(data)
    if not result: return

    weight = result['weight']
    stable = result['is_stable']

    # Tampilkan progres di console
    status = "STABIL" if stable else "MENGUKUR..."
    print(f"Data Masuk: {weight:.2f} kg ({status})")

    # JIKA STABIL: Kirim ke MQTT dan Stop
    if stable and weight > 0:
        print(f"\n[SUKSES] Berat Terukur: {weight:.2f} kg")
        
        # Format JSON sesuai standar sistem kita
        payload = json.dumps({
            "type": "berat_badan",
            "value": round(weight, 2)
        })
        
        # Publish ke topic yang didengar oleh app.py
        client_mqtt.publish(MQTT_DATA_TOPIC, payload)
        print(f"[MQTT] Data dikirim: {payload}")
        
        # Reset flag agar berhenti scanning
        should_measure = False 

async def run_ble_cycle():
    """Siklus Scan -> Connect -> Listen -> Disconnect"""
    print(f"[BLE] Mencari timbangan: {TARGET_SCALE_ADDRESS}")
    device = await BleakScanner.find_device_by_address(TARGET_SCALE_ADDRESS, timeout=10.0)
    
    if not device:
        print("[BLE] Timbangan tidak ditemukan. Pastikan timbangan menyala/diinjak.")
        return

    print(f"[BLE] Terhubung ke {device.name}...")
    try:
        async with BleakClient(device, timeout=30.0) as client:
            await client.start_notify(BODY_COMPOSITION_UUID, notification_handler)
            print("[BLE] Menunggu data stabil...")
            
            # Tunggu sampai data stabil (should_measure jadi False di handler)
            # Atau timeout setelah 30 detik
            timeout_counter = 0
            while should_measure and timeout_counter < 30:
                await asyncio.sleep(1)
                timeout_counter += 1
            
            if timeout_counter >= 30:
                print("[BLE] Waktu habis (Timeout). Tidak ada data stabil.")
                
            await client.stop_notify(BODY_COMPOSITION_UUID)
            
    except Exception as e:
        print(f"[BLE] Error koneksi: {e}")

# ====================================================================
# 3. MAIN LOOP
# ====================================================================
async def main():
    global client_mqtt
    
    # Setup MQTT
    client_mqtt = mqtt.Client()
    client_mqtt.on_connect = on_connect
    client_mqtt.on_message = on_message
    client_mqtt.connect(MQTT_BROKER, MQTT_PORT, 60)
    client_mqtt.loop_start() # Jalankan MQTT di background thread

    print("--- SERVICE TIMBANGAN BLE AKTIF ---")
    print("Menunggu perintah '6' dari Web...")

    while True:
        if should_measure:
            # Jika ada perintah (Flag 6), jalankan logika BLE
            await run_ble_cycle()
            # Setelah selesai/timeout, reset flag paksa (jika belum)
            should_measure = False 
            print("--- Selesai Sesi. Kembali Menunggu... ---")
        
        await asyncio.sleep(1) # Cek flag setiap 1 detik

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram Berhenti.")