import time
from gtts import gTTS
from pydub import AudioSegment
from pydub.playback import play
import serial
import subprocess
import requests
import json
import pandas as pd
import numpy as np
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import confusion_matrix, accuracy_score
from sklearn.preprocessing import LabelEncoder
import xgboost as xgb
import asyncio
from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError
import struct

# ==============================================================================
# === KONFIGURASI AWAL & SETTING ===
# ==============================================================================

# Setting Serial Port
portESP = 'COM7'
portUS = 'COM12'

# Variabel Global
kalt = 196
flagSapa = 0
Gula = 0
Berat = 0
Tinggi = 0
tensionmax = 0
tensionmin = 0
tensiondenyut = 0

# Status Koneksi Perangkat
scale_connected = False
tensi_connected = False

# URL API
url = 'http://103.101.52.65:7021/api/device'
url2 = 'http://103.101.52.65:7021/api/tension'
headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

# Konfigurasi BLE
SCALE_ADDRESS = "d8:e7:2f:09:84:f9"  # Ganti dengan MAC Address Timbangan Anda
TENSI_ADDRESS = "d0:20:43:20:01:2d"  # Ganti dengan MAC Address Tensimeter Anda
SCALE_SERVICE_UUID = "0000181b-0000-1000-8000-00805f9b34fb"
SCALE_CHAR_UUID = "00002a9c-0000-1000-8000-00805f9b34fb"
TENSI_SERVICE_UUID = "00001810-0000-1000-8000-00805f9b34fb"
TENSI_CHAR_UUID = "00002a35-0000-1000-8000-00805f9b34fb"

# ==============================================================================
# === FUNGSI BANTU ===
# ==============================================================================

def speak(text):
    tts = gTTS(text=text, lang='id')
    tts.save("output.mp3")
    ffplay_path = r'C:\ffmpeg\bin\ffplay.exe'
    subprocess.run([ffplay_path, "-nodisp", "-autoexit", "output.mp3"], check=True)

def parse_dataUS(data):
    Tiba = 0
    Tot = 0
    for k in range(len(data) - 4):
        if data[k] == 0xFF:
            sum = (data[k] + data[k + 1] + data[k + 2]) & 0x00FF
            if sum == data[k + 3]:
                Tiba = (data[k + 1] << 8) + data[k + 2]
                Tiba = Tiba / 10
                Tiba = (Tiba - kalt) * (-1)
                if Tiba < 50:
                    Tiba = 0
                Tot = Tiba
    return Tot

def combine_adc_value(high6Bits, low6Bits):
    """Menggabungkan dua nilai 6-bit menjadi satu nilai ADC 12-bit."""
    adc_value = (high6Bits << 6) | low6Bits
    return adc_value

def parse_dataESP(data):
    Tot = []
    i = 0
    while i < len(data) - 5:
        while i < len(data) - 2 and not (data[i] == 0xFF and data[i + 1] == 0xFE and data[i + 2] == 0xFD):
            i += 1
        
        if i < len(data) - 2 and data[i] == 0xFF and data[i + 1] == 0xFE and data[i + 2] == 0xFD:
            i += 3
            Tot = []
            for j in range(250):
                if i + 1 < len(data):
                    high6Bits = data[i]
                    low6Bits = data[i + 1]
                    Tot.append(combine_adc_value(high6Bits, low6Bits))
                    i += 2
                else:
                    break
        else:
            i += 1
    return Tot

def send_to_web(data, is_tensi=False):
    """Fungsi untuk mengirim data ke web"""
    try:
        url_to_use = url2 if is_tensi else url
        response = requests.post(url_to_use, json=data, headers=headers)
        if response.status_code == 200:
            print(f'[WEB] Data {"tensi" if is_tensi else "kesehatan"} berhasil terkirim')
            return True
        else:
            print(f'[WEB] Gagal mengirim data {"tensi" if is_tensi else "kesehatan"}')
            return False
    except Exception as e:
        print(f'[WEB] Error saat mengirim data: {e}')
        return False

# ==============================================================================
# === FUNGSI BLE UNTUK TIMBANGAN DAN TENSI ===
# ==============================================================================

def handle_scale_data(data: bytearray):
    """Menangani data dari timbangan BLE dan mengupdate variabel global."""
    global Berat, flagSapa, Gula, tensionmax, tensionmin, tensiondenyut, scale_connected
    
    length = len(data)
    if length == 13:
        ctrl_byte = data[0]
        is_stabilized = (ctrl_byte & 0x02) != 0

        if is_stabilized:
            is_catty_unit = (ctrl_byte & 0x01) != 0
            is_lbs_unit = not is_catty_unit and ((ctrl_byte & 0x10) != 0 or ctrl_byte in [0x12, 0x03])

            raw_weight = int.from_bytes(data[11:13], byteorder='little')
            parsed_weight_kg = -1.0

            if is_catty_unit: 
                parsed_weight_kg = (raw_weight / 100.0) * 0.5
            elif is_lbs_unit: 
                parsed_weight_kg = (raw_weight / 100.0) * 0.453592
            else: 
                parsed_weight_kg = raw_weight / 200.0

            if parsed_weight_kg > 0:
                Berat = parsed_weight_kg
                scale_connected = True  # Tandai bahwa timbangan terhubung
                print(f"\n[TIMBANGAN] Berat Badan: {Berat:.2f} kg")
                
                if flagSapa == 0:
                    speak("Halooo! Selamat Datang di Anjungan Kesehatan Mandiri! Silahkan periksakan kesehatan anda")
                    flagSapa = 1
                    Gula = 0
                    tensionmax = 0
                    tensionmin = 0
                    tensiondenyut = 0

def handle_tensi_data(data: bytearray):
    """Menangani data dari tensimeter BLE dan mengupdate variabel global."""
    global tensionmax, tensionmin, tensiondenyut, tensi_connected
    
    try:
        offset = 0
        flags = data[offset]
        offset += 1
        
        units_is_kpa = (flags & 0x01) != 0
        timestamp_present = (flags & 0x02) != 0
        pulse_rate_present = (flags & 0x04) != 0
        
        systolic = int.from_bytes(data[offset:offset+2], byteorder='little')
        offset += 2
        diastolic = int.from_bytes(data[offset:offset+2], byteorder='little')
        offset += 2
        offset += 2
        
        if timestamp_present:
            offset += 7 

        pulse_rate = 0
        if pulse_rate_present:
            pulse_rate = int.from_bytes(data[offset:offset+2], byteorder='little')
            offset += 2

        # Update variabel global
        tensionmax = systolic
        tensionmin = diastolic
        tensiondenyut = pulse_rate
        tensi_connected = True  # Tandai bahwa tensimeter terhubung
        
        print("\n[TENSI] Hasil Pengukuran:")
        print(f"  Tekanan Darah: {tensionmax}/{tensionmin} mmHg")
        print(f"  Denyut Nadi: {tensiondenyut} bpm")

    except Exception as e:
        print(f"[TENSI] Error saat menguraikan data: {e}")

async def monitor_ble_device(device_name: str, address: str, char_uuid: str, handler_func: callable, status_var: str):
    """Fungsi untuk memonitor perangkat BLE dengan auto-reconnect."""
    global scale_connected, tensi_connected
    
    def notification_handler(sender_handle: int, data: bytearray):
        handler_func(data)

    while True:
        try:
            print(f"Mencari {device_name} ({address})...")
            device = await BleakScanner.find_device_by_address(address, timeout=5.0)
            
            if not device:
                print(f"{device_name} tidak ditemukan. Mencoba lagi dalam 10 detik...")
                # Update status koneksi
                if device_name == "Timbangan":
                    scale_connected = False
                else:
                    tensi_connected = False
                await asyncio.sleep(10)
                continue

            print(f"Menghubungkan ke {device_name}...")
            async with BleakClient(device) as client:
                if client.is_connected:
                    print(f"Terhubung ke {device_name}. Mengaktifkan notifikasi...")
                    await client.start_notify(char_uuid, notification_handler)
                    
                    while client.is_connected:
                        await asyncio.sleep(1)
                
        except Exception as e:
            print(f"Error dengan {device_name}: {e}. Mencoba lagi...")
            # Update status koneksi
            if device_name == "Timbangan":
                scale_connected = False
            else:
                tensi_connected = False
            await asyncio.sleep(5)

# ==============================================================================
# === FUNGSI UTAMA ===
# ==============================================================================

async def main_health_monitor():
    """Fungsi utama untuk monitoring kesehatan."""
    # Inisialisasi model machine learning
    file_path = 'data ADC Glukosa.xlsx'
    df_X = pd.read_excel(file_path, sheet_name='Sheet1', header=None, usecols="A:PD", skiprows=1, nrows=250)
    X_train = df_X.to_numpy().transpose()
    
    df_Y = pd.read_excel(file_path, sheet_name='Sheet1', header=None, usecols="A:PD", nrows=1)
    Y_train = df_Y.to_numpy().flatten()
    
    label_encoder = LabelEncoder()
    Y_train_encoded = label_encoder.fit_transform(Y_train)
    
    knn = KNeighborsClassifier(n_neighbors=3)
    knn.fit(X_train, Y_train)
    
    xgb_model = xgb.XGBClassifier()
    xgb_model.fit(X_train, Y_train_encoded)
    
    # Buka port serial untuk US dan ESP
    try:
        serESP = serial.Serial(portESP, 9600, timeout=1)
        print(f"Connected to {portESP} at 9600 baud rate.")
    except serial.SerialException as e:
        print(f"Error opening ESP serial port: {e}")
        return
    
    try:
        serUS = serial.Serial(portUS, 9600, timeout=1)
        print(f"Connected to {portUS} at 9600 baud rate.")
    except serial.SerialException as e:
        print(f"Error opening US serial port: {e}")
        serESP.close()
        return
    
    # Mulai tugas BLE di background
    asyncio.create_task(monitor_ble_device("Timbangan", SCALE_ADDRESS, SCALE_CHAR_UUID, handle_scale_data, "scale_connected"))
    asyncio.create_task(monitor_ble_device("Tensimeter", TENSI_ADDRESS, TENSI_CHAR_UUID, handle_tensi_data, "tensi_connected"))
    
    # Variabel untuk pengiriman data
    dKirim = 0
    kirim2 = 0
    
    try:
        while True:
            # Baca data tinggi dari US
            serUS.reset_input_buffer()
            data = serUS.read(7)
            if data:
                Tinggi = parse_dataUS(data)
                print(f"[US] Tinggi Badan: {Tinggi:.2f} cm")
            
            # Baca data glukosa dari ESP
            if serESP.in_waiting > 0:
                data2 = serESP.read(700)
                if data2:
                    TotalESP = parse_dataESP(data2)
                    if len(TotalESP) == 250:
                        TotalESP = np.array(TotalESP).reshape(1, -1)
                        Y_predict = knn.predict(TotalESP)
                        Y_pred_xgb = xgb_model.predict(TotalESP)
                        Y_pred_xgb_decoded = label_encoder.inverse_transform(Y_pred_xgb)
                        Gula = (Y_pred_xgb_decoded[0] + Y_predict[0]) / 2
                        print(f"[GLUKOSA] Nilai Prediksi: {Gula:.2f}")
                    serESP.reset_input_buffer()
                    time.sleep(2)
            
            # Kirim data ke web setiap beberapa iterasi
            dKirim += 1
            if dKirim > 7:
                dKirim = 0
                if kirim2 == 0:
                    kirim2 = 1
                    # Kirim data kesehatan (gula, berat, tinggi)
                    dataWeb = {
                        "id": "eec58e5e-cd44-319f-a1be-46dd38c5d01c",
                        "gula": round(Gula, 2),
                        "berat": round(Berat, 2) if scale_connected else 0,  # Kirim 0 jika timbangan tidak terhubung
                        "tinggi": round(Tinggi, 2)
                    }
                    send_to_web(dataWeb)
                else:
                    kirim2 = 0
                    # Kirim data tensi hanya jika tensimeter terhubung
                    if tensi_connected:
                        dataWeb2 = {
                            "id": "fe5110fa-4b69-3c21-acfa-4c5830af6b10",
                            "b_atas": round(tensionmax, 2),
                            "b_bawah": round(tensionmin, 2),
                            "denyut": round(tensiondenyut, 2),
                        }
                        send_to_web(dataWeb2, is_tensi=True)
                    else:
                        print("[INFO] Tensimeter belum terhubung, skip pengiriman data tensi")
            
            # Tampilkan status
            print(f"\n[STATUS] Gula: {Gula:.2f} | Berat: {Berat:.2f} kg ({'Terhubung' if scale_connected else 'Tidak Terhubung'})")
            print(f"         Tinggi: {Tinggi:.2f} cm | Tensi: {'Terhubung' if tensi_connected else 'Tidak Terhubung'}")
            print(f"         Data Terakhir: {tensionmax}/{tensionmin} mmHg | Denyut: {tensiondenyut} bpm\n")
            
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("Program dihentikan oleh pengguna.")
    finally:
        serESP.close()
        serUS.close()
        print("Port serial ditutup.")

if __name__ == "__main__":
    asyncio.run(main_health_monitor())