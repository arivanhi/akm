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
from gtts import gTTS
from pydub import AudioSegment
from pydub.playback import play
import subprocess

# --- Konfigurasi Perangkat ---
SCALE_ADDRESS = "d8:e7:2f:09:84:f9"
TENSI_ADDRESS = "d0:20:43:20:01:2d"
SCALE_CHAR_UUID = "00002a9c-0000-1000-8000-00805f9b34fb"
TENSI_CHAR_UUID = "00002a35-0000-1000-8000-00805f9b34fb"
ESP_PORT = "COM7"
US_PORT = "COM12"

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
tinggi = 0.0
tensionmax = 0.0
tensionmin = 0.0
tensiondenyut = 0.0
flagSapa = 0
last_scale_data_hex = ""
last_height = 0.0
kalt = 196  # Kalibrasi ultrasonic

# --- Inisialisasi Serial Port ---
try:
    esp = serial.Serial(ESP_PORT, 9600, timeout=1)
    print(f"Connected to ESP at {ESP_PORT}")
except serial.SerialException as e:
    print(f"Error opening ESP port: {e}")
    esp = None

try:
    us = serial.Serial(US_PORT, 9600, timeout=1)
    print(f"Connected to Ultrasonic at {US_PORT}")
except serial.SerialException as e:
    print(f"Error opening Ultrasonic port: {e}")
    us = None

# --- Model KNN untuk Glukosa ---
def load_glucose_model():
    try:
        file_path = 'data ADC Glukosa.xlsx'
        sheet_name = 'Sheet1'
        
        # Baca data training
        df_X = pd.read_excel(file_path, sheet_name=sheet_name, header=None, 
                           usecols="A:PD", skiprows=1, nrows=250)
        X_train = df_X.to_numpy().T
        
        # Baca label
        df_Y = pd.read_excel(file_path, sheet_name=sheet_name, 
                           header=None, usecols="A:PD", nrows=1)
        Y_train = df_Y.to_numpy().flatten()
        
        # Encode label
        label_encoder = LabelEncoder()
        Y_train_encoded = label_encoder.fit_transform(Y_train)
        
        # Buat model KNN
        knn = KNeighborsClassifier(n_neighbors=3)
        knn.fit(X_train, Y_train)
        
        return knn, label_encoder
    except Exception as e:
        print(f"Error loading glucose model: {e}")
        return None, None

knn, label_encoder = load_glucose_model()

# --- Fungsi Text-to-Speech ---
def speak(text):
    try:
        tts = gTTS(text=text, lang='id')
        tts.save("output.mp3")
        ffplay_path = r'C:\ffmpeg\bin\ffplay.exe'
        subprocess.run([ffplay_path, "-nodisp", "-autoexit", "output.mp3"], check=True)
    except Exception as e:
        print(f"Error in TTS: {e}")

# --- Fungsi Parsing Data ---
def parse_esp_data(data):
    if len(data) < 500:
        return None
    
    for i in range(len(data) - 2):
        if data[i] == 0xFF and data[i+1] == 0xFE and data[i+2] == 0xFD:
            start = i + 3
            adc = []
            for j in range(250):
                if start + 1 >= len(data): 
                    break
                high = data[start]
                low = data[start+1]
                adc.append((high << 6) | low)
                start += 2
            return adc if len(adc) == 250 else None
    return None

def parse_us_data(data):
    global tinggi
    for k in range(len(data) - 4):
        if data[k] == 0xFF:
            sum_val = (data[k] + data[k+1] + data[k+2]) & 0x00FF
            if sum_val == data[k+3]: 
                distance = (data[k+1] << 8) + data[k+2]
                distance = distance / 10
                distance = (distance - kalt) * (-1)
                if 50 <= distance <= 220:  # Batas realistis tinggi badan manusia
                    tinggi = distance
                    print(f"[TINGGI] Tinggi badan: {tinggi:.2f} cm")
                    return tinggi
    return None

# --- BLE Scale Handler ---
def parse_scale_data(data: bytearray):
    global berat, last_scale_data_hex, flagSapa
    hex_data = data.hex()
    if hex_data == last_scale_data_hex:
        return
    
    if len(data) == 13:
        ctrl = data[0]
        if ctrl & 0x02:
            raw = int.from_bytes(data[11:13], 'little')
            if ctrl & 0x01:
                new_weight = float(round((raw / 100.0) * 0.5, 2))
            elif ctrl & 0x10:
                new_weight = float(round((raw / 100.0) * 0.453592, 2))
            else:
                new_weight = float(round(raw / 200.0, 2))
            
            if new_weight != berat:
                berat = new_weight
                print(f"[TIMBANGAN] Berat: {berat:.2f} kg")
                
                # Beri salam jika baru saja naik timbangan
                if berat > 3 and flagSapa == 0:
                    speak("Halooo! Selamat Datang di Anjungan Kesehatan Mandiri. Silahkan periksakan kesehatan anda")
                    flagSapa = 1
                
    last_scale_data_hex = hex_data

# --- BLE Tensi Handler ---
def parse_tensi_data(data: bytearray):
    global tensionmax, tensionmin, tensiondenyut
    try:
        offset = 0
        flags = data[offset]
        offset += 1
        
        timestamp = flags & 0x02
        pulse = flags & 0x04
        
        tensionmax = float(int.from_bytes(data[offset:offset+2], 'little'))
        offset += 2
        
        tensionmin = float(int.from_bytes(data[offset:offset+2], 'little'))
        offset += 2
        
        offset += 2  # Skip mean arterial pressure
        
        if timestamp:
            offset += 7
        
        if pulse:
            tensiondenyut = float(int.from_bytes(data[offset:offset+2], 'little'))
        
        print(f"[TENSI] {tensionmax:.1f}/{tensionmin:.1f} mmHg, Denyut: {tensiondenyut:.1f} bpm")
    except Exception as e:
        print(f"[TENSI] Gagal parsing data: {e}")

# --- Pembacaan Data ESP (Glukosa) ---
async def get_esp_gula():
    global gula
    if esp is None or knn is None:
        return
    
    try:
        esp.reset_input_buffer()
        data = esp.read(700)
        adc_data = parse_esp_data(data)
        
        if adc_data and len(adc_data) == 250:
            arr = np.array(adc_data).reshape(1, -1)
            pred_knn = knn.predict(arr)[0]
            pred_label = label_encoder.inverse_transform(knn.predict(arr))[0]
            gula = float(round((float(pred_knn) + float(pred_label)) / 2, 2))
            print(f"[GULA] Prediksi: {gula:.2f} mg/dL")
    except Exception as e:
        print(f"[GULA] Error: {e}")

# --- Pembacaan Data Ultrasonic (Tinggi Badan) ---
async def get_tinggi_badan():
    global tinggi
    if us is None:
        return
    
    try:
        us.reset_input_buffer()
        data = us.read(7)
        parse_us_data(data)
    except Exception as e:
        print(f"[TINGGI] Error: {e}")

# --- BLE Monitor ---
async def monitor_device(name, address, uuid, handler):
    def notify_handler(_, data):
        handler(data)
    
    while True:
        try:
            print(f"[BLE] Mencari {name}...")
            device = await BleakScanner.find_device_by_address(address, timeout=5.0)
            if device is None:
                print(f"[BLE] {name} tidak ditemukan")
                await asyncio.sleep(10)
                continue
            
            print(f"[BLE] Terhubung ke {name}")
            async with BleakClient(device) as client:
                await client.start_notify(uuid, notify_handler)
                while client.is_connected:
                    await asyncio.sleep(1)
                
        except Exception as e:
            print(f"[BLE] Error {name}: {e}")
        await asyncio.sleep(5)

# --- Kirim Data ke Server ---
async def loop_kirim_data():
    while True:
        # Ambil data terbaru
        await get_esp_gula()
        await get_tinggi_badan()
        
        print(f"[DATA] Gula: {gula:.2f} mg/dL, Berat: {berat:.2f} kg, Tinggi: {tinggi:.2f} cm")
        print(f"[DATA] Tensi: {tensionmax:.1f}/{tensionmin:.1f} mmHg, Denyut: {tensiondenyut:.1f} bpm")
        
        # Siapkan data untuk dikirim
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
        
        # Kirim data
        try:
            r1 = requests.post(url, json=dataWeb, headers=headers, timeout=5)
            print(f"[WEB] Kirim gula/berat/tinggi: {r1.status_code}")
            
            r2 = requests.post(url2, json=dataWeb2, headers=headers, timeout=5)
            print(f"[WEB] Kirim tensi: {r2.status_code}")
            
        except Exception as e:
            print(f"[WEB] Error kirim data: {e}")
        
        await asyncio.sleep(10)

# --- Main Program ---
async def main():
    tasks = [
        monitor_device("Timbangan", SCALE_ADDRESS, SCALE_CHAR_UUID, parse_scale_data),
        monitor_device("Tensimeter", TENSI_ADDRESS, TENSI_CHAR_UUID, parse_tensi_data),
        loop_kirim_data()
    ]
    
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[SYSTEM] Program dihentikan")
        if esp and esp.is_open:
            esp.close()
        if us and us.is_open:
            us.close()
    except Exception as e:
        print(f"[SYSTEM] Error: {e}")