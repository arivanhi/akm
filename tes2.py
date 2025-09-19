import asyncio
import sys
import struct
import time
import requests
from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError
import numpy as np
import pandas as pd
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import LabelEncoder
import serial
import xgboost as xgb

# --- Konfigurasi Perangkat BLE ---
SCALE_ADDRESS = "d8:e7:2f:09:84:f9"
TENSI_ADDRESS = "d0:20:43:20:01:2d"
SCALE_CHAR_UUID = "00002a9c-0000-1000-8000-00805f9b34fb"
TENSI_CHAR_UUID = "00002a35-0000-1000-8000-00805f9b34fb"

# --- Konfigurasi ESP ---
ESP_PORT = "COM7"
esp = serial.Serial(ESP_PORT, 9600, timeout=1)

# --- Konfigurasi Web ---
url = 'http://103.101.52.65:7021/api/device'
url2 = 'http://103.101.52.65:7021/api/tension'
headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

# --- Variabel Global ---
gula = 0.0
berat = 0.0
tinggi = 170.0  # Tambahkan default tinggi

# Pastikan tinggi dikirim sebagai floatimport
if not isinstance(tinggi, float):
    tinggi = float(tinggi)

tensionmax = 0.0
tensionmin = 0.0
tensiondenyut = 0.0

file_path = 'data ADC Glukosa.xlsx'
sheet_name = 'Sheet1'
df = pd.read_excel(file_path, sheet_name=sheet_name)

# Membaca data dari sheet 1, mulai dari A2 ke EE300 untuk X
df_X = pd.read_excel(file_path, sheet_name='Sheet1', header=None, usecols="A:PD", skiprows=1, nrows=250)

# Mengambil nilai X dari DataFrame dan mengonversinya ke numpy array
X_train = df_X.to_numpy()
X_train = np.transpose(X_train)

# Membaca data dari sheet 1, mulai dari A1 ke EE1 untuk Y
df_Y = pd.read_excel(file_path, sheet_name='Sheet1', header=None, usecols="A:PD", nrows=1)

Y_train = df_Y.to_numpy().flatten()

# Encode target classes
label_encoder = LabelEncoder()
Y_train_encoded = label_encoder.fit_transform(Y_train)

# Menampilkan dimensi X_train dan Y_train untuk memeriksa jumlah sampel
print("Dimensi X_train:", X_train.shape)
print("Dimensi Y_train:", Y_train.shape)

# Cetak X_train dan Y_train untuk memeriksa
print("Data X_train (sample data):")
print(X_train)

print("\nData Y_train (hasil) setelah diencode:")
print(Y_train)

# Membuat model KNN
knn = KNeighborsClassifier(n_neighbors=3)  # Jumlah tetangga bisa disesuaikan
knn.fit(X_train, Y_train)
# Membuat dan melatih model XGBoost
xgb_model = xgb.XGBClassifier()
xgb_model.fit(X_train, Y_train_encoded)


# --- Fungsi Parsing ESP ---
def parse_esp_data(data):
    if len(data) < 500:
        return 0.0
    for i in range(len(data) - 2):
        if data[i] == 0xFF and data[i+1] == 0xFE and data[i+2] == 0xFD:
            start = i + 3
            adc = []
            for j in range(250):
                if start + 1 >= len(data): break
                high = data[start]
                low = data[start+1]
                adc.append((high << 6) | low)
                start += 2
            return adc if len(adc) == 250 else 0.0
    return 0.0

async def get_esp_gula():
    global gula
    esp.reset_input_buffer()
    data = esp.read(700)
    result = parse_esp_data(data)
    if isinstance(result, list):
        arr = np.array(result).reshape(1, -1)
        pred = knn.predict(arr)
        gula = float(round((float(pred[0]) + float(label_encoder.inverse_transform(knn.predict(arr))[0])) / 2, 2))

# --- BLE Scale ---
last_scale_data_hex = ""
def parse_scale_data(data: bytearray):
    global berat, last_scale_data_hex
    hex_data = data.hex()
    if hex_data == last_scale_data_hex:
        return
    if len(data) == 13:
        ctrl = data[0]
        if ctrl & 0x02:
            raw = int.from_bytes(data[11:13], 'little')
            if ctrl & 0x01:
                berat = float(round((raw / 100.0) * 0.5, 2))
            elif ctrl & 0x10:
                berat = float(round((raw / 100.0) * 0.453592, 2))
            else:
                berat = float(round(raw / 200.0, 2))
            print(f"[TIMBANGAN] Berat: {berat:.2f} kg")
    last_scale_data_hex = hex_data

# --- BLE Tensi ---
def parse_tensi_data(data: bytearray):
    global tensionmax, tensionmin, tensiondenyut
    try:
        offset = 0
        flags = data[offset]
        offset += 1
        timestamp = flags & 0x02
        pulse = flags & 0x04
        tensionmax = float(int.from_bytes(data[offset:offset+2], 'little')); offset += 2
        tensionmin = float(int.from_bytes(data[offset:offset+2], 'little')); offset += 2
        offset += 2
        if timestamp:
            offset += 7
        if pulse:
            tensiondenyut = float(int.from_bytes(data[offset:offset+2], 'little'))
        print(f"[TENSI] {tensionmax}/{tensionmin} mmHg, Pulse: {tensiondenyut} bpm")
    except Exception as e:
        print(f"Gagal parsing tensimeter: {e}")

# --- BLE Monitor ---
async def monitor_device(name, address, uuid, handler):
    def notify_handler(_, data):
        handler(data)
    while True:
        try:
            print(f"[BLE] Mencari {name}...")
            device = await BleakScanner.find_device_by_address(address, timeout=5.0)
            if device is None:
                await asyncio.sleep(10); continue
            print(f"[BLE] Terhubung ke {name}")
            async with BleakClient(device) as client:
                await client.start_notify(uuid, notify_handler)
                while client.is_connected:
                    await asyncio.sleep(1)
        except Exception as e:
            print(f"[BLE] Error {name}: {e}")
        await asyncio.sleep(5)

# --- Kirim Data ---
async def loop_kirim_data():
    global tinggi
    while True:
        await get_esp_gula()
        print(f"[DATA] Gula: {gula:.2f}, Berat: {berat:.2f}, Tinggi: {tinggi:.2f}, Tensi: {tensionmax:.2f}/{tensionmin:.2f}, Denyut: {tensiondenyut:.2f}")
        dataWeb = {
            "id": "eec58e5e-cd44-319f-a1be-46dd38c5d01c",
            "gula": float(gula),
            "berat": float(berat),
            "tinggi": float(tinggi)
        }
        dataWeb2 = {
            "id": "fe5110fa-4b69-3c21-acfa-4c5830af6b10",
            "b_atas": float(tensionmax),
            "b_bawah": float(tensionmin),
            "denyut": float(tensiondenyut)
        }
        try:
            r1 = requests.post(url, json=dataWeb, headers=headers)
            print(f"[WEB] Kirim gula/berat/tinggi: {r1.status_code} => {dataWeb}")
            r2 = requests.post(url2, json=dataWeb2, headers=headers)
            print(f"[WEB] Kirim tensi: {r2.status_code} => {dataWeb2}")
        except Exception as e:
            print(f"[WEB] Error kirim: {e}")
        await asyncio.sleep(10)

# --- Main ---
async def main():
    await asyncio.gather(
        monitor_device("Timbangan", SCALE_ADDRESS, SCALE_CHAR_UUID, parse_scale_data),
        monitor_device("Tensimeter", TENSI_ADDRESS, TENSI_CHAR_UUID, parse_tensi_data),
        loop_kirim_data()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[SYSTEM] Dihentikan.")