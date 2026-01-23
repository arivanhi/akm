import asyncio
import time
import paho.mqtt.client as mqtt
from bleak import BleakClient, BleakScanner

# ====================================================================
# KONFIGURASI MQTT (Sesuai Node-RED)
# ====================================================================
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_CMD_TOPIC = "akm/command"      # Node-RED kirim perintah kesini (5 atau 6)
MQTT_DATA_TOPIC = "akm/sensor_raw"  # Python kirim data kesini (format: tipe:nilai)
MQTT_STATUS_TOPIC = "akm/connect"   # Status koneksi alat

# ====================================================================
# KONFIGURASI PERANGKAT BLE
# ====================================================================
# 1. TIMBANGAN (Weight Scale) - Xiaomi / Generic
WEIGHT_ADDRESS = "d8:e7:2f:0a:94:44" 
WEIGHT_UUID = "00002a9c-0000-1000-8000-00805f9b34fb"

# 2. PENGUKUR TINGGI (Height Scale) - ESP32
HEIGHT_NAME = "bleScaleHeight"
HEIGHT_CHAR_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"

# ====================================================================
# GLOBAL STATE
# ====================================================================
mqtt_client = None

# State Berat Badan
weight_state = {
    "latest": 0.0,
    "stable": False,
    "connected": False,
    "capture_request": False  # Flag aktif jika terima command '6'
}

# State Tinggi Badan
height_state = {
    "latest": 0.0,
    "connected": False,
    "capture_request": False  # Flag aktif jika terima command '5'
}

# ====================================================================
# 1. LOGIKA MQTT (Handled by Node-RED Logic)
# ====================================================================
def on_connect(client, userdata, flags, rc):
    print(f"[MQTT] Terhubung ke Broker. Siap menerima perintah dari Node-RED.")
    client.subscribe(MQTT_CMD_TOPIC)

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode("utf-8").strip()
        
        # --- COMMAND '6': AMBIL BERAT BADAN ---
        if payload == "6":
            print(f"[COMMAND] Node-RED meminta Berat Badan (6).")
            if not weight_state["connected"]:
                print("[WARNING] Timbangan belum terhubung.")
                return
            
            # Jika data sudah stabil saat ini, langsung kirim
            if weight_state["stable"] and weight_state["latest"] > 0:
                publish_data("berat_badan", weight_state["latest"])
                weight_state["capture_request"] = False
            else:
                # Jika belum stabil, set flag tunggu
                print("[INFO] Menunggu timbangan stabil...")
                weight_state["capture_request"] = True

        # --- COMMAND '5': AMBIL TINGGI BADAN ---
        elif payload == "5":
            print(f"[COMMAND] Node-RED meminta Tinggi Badan (5).")
            # Set flag, tunggu data masuk dari sensor
            height_state["capture_request"] = True

    except Exception as e:
        print(f"[MQTT] Error: {e}")

def publish_data(tipe, nilai):
    """Kirim data ke Node-RED via MQTT"""
    payload_str = f"{tipe}:{round(nilai, 2)}"
    mqtt_client.publish(MQTT_DATA_TOPIC, payload_str)
    print(f"[SUCCESS] Dikirim ke Node-RED: {payload_str}")

# ====================================================================
# 2. TASK TIMBANGAN (Weight Scale)
# ====================================================================
def parse_weight_data(data: bytearray):
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

def weight_notification_handler(sender, data):
    res = parse_weight_data(data)
    if not res: return

    weight_state["latest"] = res['val']
    weight_state["stable"] = res['stable']

    # LOGIKA PENGIRIMAN:
    # Hanya kirim jika Node-RED meminta (flag=True) DAN data stabil
    if weight_state["capture_request"] and weight_state["stable"] and weight_state["latest"] > 0:
        publish_data("berat_badan", weight_state["latest"])
        weight_state["capture_request"] = False # Reset permintaan

async def run_weight_scale():
    print("--- Service Timbangan (Weight) Dimulai ---")
    while True:
        weight_state["connected"] = False
        try:
            device = await BleakScanner.find_device_by_address(WEIGHT_ADDRESS, timeout=5.0)
            if device:
                print("[WEIGHT] Timbangan ditemukan! Menghubungkan...")
                async with BleakClient(device, timeout=30.0) as client:
                    mqtt_client.publish(MQTT_STATUS_TOPIC, "connected_ble_scale")
                    weight_state["connected"] = True
                    print("[WEIGHT] TERHUBUNG!")
                    
                    await client.start_notify(WEIGHT_UUID, weight_notification_handler)
                    
                    while client.is_connected:
                        await asyncio.sleep(1)
                    print("[WEIGHT] Putus.")
            else:
                pass 
        except Exception as e:
            print(f"[WEIGHT] Error: {e}")
            mqtt_client.publish(MQTT_STATUS_TOPIC, "disconnected_ble_scale")
        
        await asyncio.sleep(2)

# ====================================================================
# 3. TASK TINGGI BADAN (Height Scale)
# ====================================================================
def height_notification_handler(sender, data):
    try:
        # Decode data dari ESP32 (String UTF-8)
        received_string = data.decode('utf-8').strip()
        val = float(received_string)
        
        height_state["latest"] = val
        # print(f"[HEIGHT DEBUG] {val} cm") # Uncomment untuk lihat raw stream

        # LOGIKA PENGIRIMAN:
        # Jika Node-RED minta (flag=True), langsung kirim nilai terbaru
        if height_state["capture_request"]:
            publish_data("tinggi_badan", val)
            height_state["capture_request"] = False # Reset permintaan

    except Exception as e:
        print(f"[HEIGHT] Error decode: {e}")

async def run_height_scale():
    print("--- Service Tinggi Badan (Height) Dimulai ---")
    while True:
        height_state["connected"] = False
        try:
            device = await BleakScanner.find_device_by_name(HEIGHT_NAME, timeout=5.0)
            if device:
                print("[HEIGHT] Alat Tinggi ditemukan! Menghubungkan...")
                async with BleakClient(device) as client:
                    height_state["connected"] = True
                    print("[HEIGHT] TERHUBUNG!")
                    
                    await client.start_notify(HEIGHT_CHAR_UUID, height_notification_handler)
                    
                    while client.is_connected:
                        await asyncio.sleep(1)
                    print("[HEIGHT] Putus.")
            else:
                pass
        except Exception as e:
            print(f"[HEIGHT] Error: {e}")
        
        await asyncio.sleep(2)

# ====================================================================
# MAIN
# ====================================================================
async def main():
    global mqtt_client
    
    # 1. Konek MQTT
    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
    except Exception as e:
        print(f"Gagal konek MQTT: {e}")
        return

    # 2. Jalankan kedua loop sensor BLE secara paralel
    await asyncio.gather(
        run_weight_scale(),
        run_height_scale()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStop.")