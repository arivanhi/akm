import asyncio
import struct
import time
import requests
import numpy as np
import pandas as pd
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import LabelEncoder
import xgboost as xgb
from bleak import BleakClient, BleakScanner
import serial

# BLE address dan UUID
SCALE_ADDRESS = "d8:e7:2f:09:84:f9"
TENSI_ADDRESS = "d0:20:43:20:01:2d"
SCALE_UUID = "00002a9c-0000-1000-8000-00805f9b34fb"
TENSI_UUID = "00002a35-0000-1000-8000-00805f9b34fb"

# Serial Port
ESP_PORT = "COM7"
US_PORT = "COM12"
esp = serial.Serial(ESP_PORT, 9600, timeout=1)
us = serial.Serial(US_PORT, 9600, timeout=1)
kalt = 196

# Load Model Glukosa
df_X = pd.read_excel("data ADC Glukosa.xlsx", sheet_name="Sheet1", header=None, usecols="A:PD", skiprows=1, nrows=250)
df_Y = pd.read_excel("data ADC Glukosa.xlsx", sheet_name="Sheet1", header=None, usecols="A:PD", nrows=1)
X_train = df_X.to_numpy().T
Y_train = df_Y.to_numpy().flatten()
label_encoder = LabelEncoder()
Y_train_encoded = label_encoder.fit_transform(Y_train)
knn = KNeighborsClassifier(n_neighbors=3).fit(X_train, Y_train)
xgb_model = xgb.XGBClassifier().fit(X_train, Y_train_encoded)

# Variabel global
berat = 0.0
tinggi = 0.0
gula = 0.0
tensionmax = 0.0
tensionmin = 0.0
tensiondenyut = 0.0

# Endpoint Web
url = 'http://103.101.52.65:7021/api/device'
url2 = 'http://103.101.52.65:7021/api/tension'
headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}

# BLE Handler
def parse_scale(data: bytearray):
    global berat
    if len(data) == 13:
        ctrl = data[0]
        raw = int.from_bytes(data[11:13], 'little')
        if ctrl & 0x02:
            berat = round((raw / 200.0), 2)
            print(f"[BLE] Berat: {berat:.2f} kg")

def parse_tensi(data: bytearray):
    global tensionmax, tensionmin, tensiondenyut
    try:
        offset = 1
        tensionmax = int.from_bytes(data[offset:offset+2], 'little')
        offset += 2
        tensionmin = int.from_bytes(data[offset:offset+2], 'little')
        offset += 2 + 2  # Skip MAP
        tensiondenyut = int.from_bytes(data[offset+7:offset+9], 'little')
        print(f"[BLE] Tensi: {tensionmax}/{tensionmin}, Denyut: {tensiondenyut}")
    except Exception as e:
        print("[BLE] Tensi Error:", e)

# Serial Parse
def parse_esp(data):
    for i in range(len(data)-3):
        if data[i:i+3] == b'\xFF\xFE\xFD':
            start = i + 3
            adc = [(data[start+i*2]<<6 | data[start+i*2+1]) for i in range(250) if start+i*2+1 < len(data)]
            return adc if len(adc) == 250 else None
    return None

def parse_us(data):
    global tinggi
    for i in range(len(data)-4):
        if data[i] == 0xFF:
            total = (data[i] + data[i+1] + data[i+2]) & 0xFF
            if total == data[i+3]:
                dist = ((data[i+1] << 8) + data[i+2]) / 10
                tinggi = (dist - kalt) * -1
                print(f"[SERIAL] Tinggi: {tinggi:.2f} cm")

# BLE Notif Loop
async def read_ble(address, uuid, handler):
    while True:
        device = await BleakScanner.find_device_by_address(address, timeout=5)
        if device:
            async with BleakClient(device) as client:
                await client.start_notify(uuid, lambda _, d: handler(d))
                while client.is_connected:
                    await asyncio.sleep(1)
        await asyncio.sleep(5)

# Main Loop
async def main_loop():
    global gula
    while True:
        # Tinggi badan
        us.reset_input_buffer()
        parse_us(us.read(7))

        # Gula darah
        esp.reset_input_buffer()
        data = esp.read(700)
        adc = parse_esp(data)
        if adc:
            arr = np.array(adc).reshape(1, -1)
            pred_knn = knn.predict(arr)[0]
            pred_xgb = label_encoder.inverse_transform(xgb_model.predict(arr))[0]
            gula = round((float(pred_knn) + float(pred_xgb)) / 2, 2)
            print(f"[GULA] Prediksi: {gula} mg/dL")

        # Kirim ke Web
        data1 = {
            "id": "eec58e5e-cd44-319f-a1be-46dd38c5d01c",
            "gula": gula,
            "berat": berat,
            "tinggi": tinggi
        }
        data2 = {
            "id": "fe5110fa-4b69-3c21-acfa-4c5830af6b10",
            "b_atas": tensionmax,
            "b_bawah": tensionmin,
            "denyut": tensiondenyut
        }
        try:
            r1 = requests.post(url, json=data1, headers=headers)
            r2 = requests.post(url2, json=data2, headers=headers)
            print(f"[WEB] POST Status: {r1.status_code} / {r2.status_code}")
        except Exception as e:
            print("[WEB] Error:", e)

        await asyncio.sleep(10)

# Run semua
async def main():
    await asyncio.gather(
        read_ble(SCALE_ADDRESS, SCALE_UUID, parse_scale),
        read_ble(TENSI_ADDRESS, TENSI_UUID, parse_tensi),
        main_loop()
    )

try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("Program dihentikan.")
finally:
    if esp.is_open: esp.close()
    if us.is_open: us.close()
