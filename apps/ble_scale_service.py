import asyncio
import json
import time
import traceback
import paho.mqtt.client as mqtt
from bleak import BleakClient, BleakScanner

# --- KONFIGURASI ---
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_CMD_TOPIC = "akm/command"
MQTT_DATA_TOPIC = "akm/prediction_data"

TARGET_SCALE_ADDRESS = "d8:e7:2f:0a:94:44" # MAC Address Timbangan
BODY_COMPOSITION_UUID = "00002a9c-0000-1000-8000-00805f9b34fb"

# --- STATE GLOBAL ---
latest_weight = 0.0
is_stable = False
is_connected = False
capture_request = False # Flag saat user minta data (angka 6)
mqtt_client = None


# ====================================================================
# 1. LOGIKA MQTT (Hanya Memicu Pengambilan Data)
# ====================================================================
def on_connect(client, userdata, flags, rc):
    print(f"[MQTT] Terhubung ke Broker. Siap menerima perintah.")
    client.subscribe(MQTT_CMD_TOPIC)

def on_message(client, userdata, msg):
    global capture_request, latest_weight, is_stable, is_connected
    
    try:
        payload = msg.payload.decode("utf-8")
        # Jika perintah '6' diterima
        if payload.strip() == "6":
            print(f"[COMMAND] Permintaan ambil data berat badan diterima.")
            
            # Cek status koneksi saat ini
            if not is_connected:
                print("[ERROR] Timbangan belum terhubung! Injak timbangan dulu.")
                # Opsional: Bisa kirim feedback error ke web lewat MQTT jika mau
                return
            
            time.sleep(3)

            if is_stable and latest_weight > 0:
                # KASUS 1: Data sudah ada dan stabil (Langsung kirim)
                send_data_to_web(latest_weight)
            else:
                # KASUS 2: Terhubung, tapi belum stabil (Set flag, tunggu stabil)
                print("[INFO] Menunggu timbangan stabil...")
                capture_request = True 

    except Exception as e:
        print(f"[MQTT] Error: {e}")

def send_data_to_web(weight):
    global mqtt_client, capture_request
    
    # payload = json.dumps({
    #     "type": "berat_badan",
    #     "value": round(weight, 2)
    # })
    # mqtt_client.publish(MQTT_DATA_TOPIC, payload)
    # print(f"[SUCCESS] Data {weight} kg dikirim ke Web!")
    
    # # Reset flag permintaan
    # capture_request = False
    payload_str = f"berat_badan:{round(weight, 2)}"
    mqtt_client.publish("akm/sensor_raw", payload_str) 
    
    print(f"[SUCCESS] Data dikirim ke Node-RED: {payload_str}")
    
    # Reset flag permintaan
    capture_request = False

# ====================================================================
# 2. LOGIKA BLE (Auto Connect & Listen)
# ====================================================================
def parse_data(data: bytearray):
    if len(data) < 13: return None
    
    ctrl_byte = data[0]
    stable = (ctrl_byte & 0x02) != 0
    catty = (ctrl_byte & 0x01) != 0
    lbs = (ctrl_byte & 0x10) != 0

    raw = int.from_bytes(data[11:13], byteorder='little')
    kg = 0.0

    if catty: kg = (raw / 100.0) * 0.5
    elif lbs: kg = (raw / 100.0) * 0.453592
    else: kg = raw / 200.0 

    return {"val": kg, "stable": stable}

def notification_handler(sender, data):
    global latest_weight, is_stable, capture_request
    
    res = parse_data(data)
    if not res: return

    latest_weight = res['val']
    is_stable = res['stable']

    # Log ringan biar tidak spam (opsional)
    # print(f"Berat: {latest_weight} kg | Stabil: {is_stable}")

    # LOGIKA PENTING:
    # Jika user SUDAH minta (flag 6 aktif) DAN data SEKARANG stabil
    if capture_request and is_stable and latest_weight > 0:
        send_data_to_web(latest_weight)

async def connection_loop():
    global is_connected, latest_weight, is_stable
    
    print("--- MEMULAI SERVICE AUTO-CONNECT ---")
    
    while True:
        is_connected = False
        is_stable = False
        
        print(f"[BLE] Mencari timbangan ({TARGET_SCALE_ADDRESS})...")
        try:
            # Scan dulu untuk memastikan perangkat ada dalam jangkauan (agar tidak error saat connect)
            device = await BleakScanner.find_device_by_address(TARGET_SCALE_ADDRESS, timeout=5.0)
            
            if device:
                print(f"[BLE] Timbangan ditemukan! Menghubungkan...")
                mqtt_client.publish("akm/connect", "connected_ble_scale") 
                
                async with BleakClient(device, timeout=30.0) as client:
                    mqtt_client.publish("akm/connect", "connected_ble_scale")
                    is_connected = True
                    print(f"[BLE] TERHUBUNG! Menunggu user naik...")
                     
            
                    counter_seconds = 0
                    
                    await client.start_notify(BODY_COMPOSITION_UUID, notification_handler)
                    
                    # Loop untuk menjaga koneksi tetap hidup selama timbangan menyala
                    while client.is_connected:
                        await asyncio.sleep(1)
                        counter_seconds += 1
                        print(f"[BLE] Terhubung: {counter_seconds} detik", end='\r') # end='\r' agar log satu baris (opsional)
                        # Timbangan Xiaomi otomatis putus koneksi jika layar mati (hemat baterai)
                        # Jadi loop ini akan pecah otomatis saat itu terjadi.
                    
                    print("[BLE] Timbangan putus (Layar mati/Jauh).")
                    
            else:
                # Tidak ketemu, coba lagi nanti
                pass

        except Exception as e:
            print(f"[BLE] Error (Retrying...): {e}")
            mqtt_client.publish("akm/connect", "disconnected_ble_scale")
            # traceback.print_exc() # Uncomment jika butuh detail
        
        # Jeda sebelum scan ulang agar tidak membebani CPU
        await asyncio.sleep(2)

# ====================================================================
# 3. MAIN
# ====================================================================
async def main():
    global mqtt_client
    
    # Setup MQTT
    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
    except:
        print("Gagal konek MQTT Broker")

    # Jalankan loop BLE selamanya
    await connection_loop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Berhenti.")