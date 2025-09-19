import time
import threading # PERUBAHAN: Import library threading
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
import asyncio
import sys
from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError
import struct
import datetime
import xgboost as xgb
#from DFRobot_RaspberryPi_A02YYUW import DFRobot_A02_Distance as Board
time.sleep(5)

# Setting
# Variabel global untuk menyimpan data dari BLE
last_scale_data_hex = ""
bleScale = 0.0
bleSys = 0
bleDias = 0
bleBPM = 0

# --- Alamat MAC Perangkat ---
SCALE_ADDRESS = "d8:e7:2f:09:84:f9" # Timbangan Mi Scale/MIBFS
TENSI_ADDRESS = "d0:20:43:20:01:2d"  # Yuwell Tensimeter

# --- UUIDs Timbangan ---
SCALE_SERVICE_UUID = "0000181b-0000-1000-8000-00805f9b34fb"
SCALE_CHAR_UUID = "00002a9c-0000-1000-8000-00805f9b34fb"

# --- UUIDs Tensimeter ---
TENSI_SERVICE_UUID = "00001810-0000-1000-8000-00805f9b34fb"
TENSI_CHAR_UUID = "00002a35-0000-1000-8000-00805f9b34fb"

# Setting port serial dan variabel lainnya
portESP = 'COM7'
portUS = 'COM12'
kalt = 196
Total = 0
flagSapa = 0
dKirim = 0
kirim2 = 0
Tinggi = 0
Gula = 0
glukosa = ''

##############TRAIN########################
# Baca file Excel
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

def parse_scale_data(data: bytearray):
    global last_scale_data_hex, bleScale
    current_data_hex = data.hex()
    if current_data_hex == last_scale_data_hex: return

    if len(data) == 13:
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
                # print(f"--- [TIMBANGAN] Data diterima: {parsed_weight_kg:.2f} kg ---")
                bleScale = parsed_weight_kg
                last_scale_data_hex = current_data_hex
                
def parse_tensimeter_data(data: bytearray):
    global bleSys, bleDias, bleBPM
    try:
        offset = 0
        flags = data[offset]; offset += 1
        timestamp_present = (flags & 0x02) != 0
        pulse_rate_present = (flags & 0x04) != 0
        
        systolic = int.from_bytes(data[offset:offset+2], byteorder='little'); offset += 2
        diastolic = int.from_bytes(data[offset:offset+2], byteorder='little'); offset += 2
        offset += 2 # Lewati MAP
        if timestamp_present: offset += 7 

        pulse_rate = 0
        if pulse_rate_present:
            pulse_rate = int.from_bytes(data[offset:offset+2], byteorder='little')
        
        bleSys, bleDias, bleBPM = systolic, diastolic, pulse_rate
        # print(f"--- [TENSIMETER] Data diterima: {systolic}/{diastolic} mmHg, Nadi: {pulse_rate} bpm ---")
        
    except Exception as e:
        print(f"[TENSIMETER] Error parsing: {e}")
        
async def monitor_device(device_name: str, address: str, char_uuid: str, parser_func: callable):
    """Fungsi generik untuk memonitor satu perangkat BLE dengan auto-reconnect."""
    def notification_handler(sender_handle: int, data: bytearray):
        parser_func(data)

    # PERUBAHAN: Loop berjalan selamanya karena tidak ada lagi tombol 'q'
    while True:
        try:
            print(f"[BLE Thread] Mencari {device_name} ({address})...")
            device = await BleakScanner.find_device_by_address(address, timeout=5.0)
            
            if not device:
                print(f"[BLE Thread] {device_name} tidak ditemukan. Mencoba lagi dalam 5 detik...")
                await asyncio.sleep(5)
                continue

            print(f"[BLE Thread] Menghubungkan ke {device_name}...")
            async with BleakClient(device) as client:
                if client.is_connected:
                    print(f"[BLE Thread] Terhubung ke {device_name}. Mengaktifkan notifikasi...")
                    await client.start_notify(char_uuid, notification_handler)
                    while client.is_connected:
                        await asyncio.sleep(1)
                    print(f"[BLE Thread] Koneksi ke {device_name} terputus.")
                
        except Exception as e:
            print(f"[BLE Thread] Error dengan {device_name}: {e}. Mencoba lagi...")
        await asyncio.sleep(5) # Jeda sebelum mencoba menghubungkan kembali
        
async def ble_main_task():
    """Fungsi utama untuk menjalankan semua tugas BLE secara bersamaan."""
    scale_task = asyncio.create_task(monitor_device("Timbangan", SCALE_ADDRESS, SCALE_CHAR_UUID, parse_scale_data))
    tensi_task = asyncio.create_task(monitor_device("Tensimeter", TENSI_ADDRESS, TENSI_CHAR_UUID, parse_tensimeter_data))
    await asyncio.gather(scale_task, tensi_task)
    
def start_ble_monitoring():
    """Fungsi yang akan dijalankan oleh thread baru untuk memulai loop asyncio."""
    print("[BLE Thread] Memulai loop event asyncio...")
    asyncio.run(ble_main_task())

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
            sum=(data[k]+data[k+1]+data[k+2])&0x00FF
            if sum == data[k+3]: 
                Tiba = (data[k+1]<<8)+data[k+2]
                Tiba = Tiba/10
                Tiba = (Tiba - kalt) * (-1);
                if Tiba<50:
                    Tiba = 0
            #else:
            #    Tiba = 200       
            Tot = Tiba
    return Tot

def combine_adc_value(high6Bits, low6Bits):
    """Menggabungkan dua nilai 6-bit menjadi satu nilai ADC 12-bit."""
    adc_value = (high6Bits << 6) | low6Bits
    return adc_value

def parse_dataESP(data):
    Tot = []
    i = 0
    while i < len(data) - 5:  # Periksa setidaknya ada 6 byte tersisa untuk diproses
        # Temukan pola FF FE FD setelah sekitar 150 byte 0 awal
        while i < len(data) - 2 and not (data[i] == 0xFF and data[i+1] == 0xFE and data[i+2] == 0xFD):
            i += 1
        
        # Jika menemukan pola FF FE FD
        if i < len(data) - 2 and data[i] == 0xFF and data[i+1] == 0xFE and data[i+2] == 0xFD:
            i += 3  # Lanjutkan melewati pola header
            Tot = []
            # Proses 300 pasang 6-bit data yang diharapkan
            for j in range(250):
                if i + 1 < len(data):
                    high6Bits = data[i]
                    low6Bits = data[i + 1]
                    Tot.append(combine_adc_value(high6Bits, low6Bits))
                    i += 2  # Lanjutkan ke pasangan berikutnya dari 6-bit data
                else:
                    break  # Jika tidak ada cukup data untuk diproses, keluar dari loop
        
        else:
            i += 1  # Lanjutkan mencari tanda awal yang valid setelah 150 data 0 awal

    return Tot

##################################################
# URL API untuk mengirim data
url = 'http://103.101.52.65:7021/api/device'
url2 ='http://103.101.52.65:7021/api/tension'
url3 ='http://cemti.org/api_glukosa/update/1' #endpoint web cemti

# Header sesuai dengan aturan yang diberikan
headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

headers2 = {
    'Content-Type': 'application/json',
}

try:
    serESP = serial.Serial(portESP, 9600, timeout=1)
    print(f"Connected to {portESP} at 9600 baud rate.")
except serial.SerialException as e:
    print(f"Error opening or reading from serial port: {e}")
except KeyboardInterrupt:
    print("Exiting program.")

try:
    serUS = serial.Serial(portUS, 9600, timeout=1)
    print(f"Connected to {portUS} at 9600 baud rate.")
except serial.SerialException as e:
    print(f"Error opening or reading from serial port: {e}")
except KeyboardInterrupt:
    print("Exiting program.")

ble_thread = threading.Thread(target=start_ble_monitoring, daemon=True)
ble_thread.start()
print("Sistem monitoring BLE berjalan di background...")
time.sleep(2) # Beri waktu sedikit untuk thread BLE mulai

try:
    while True:
        now = datetime.datetime.now()
        current_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
        # Reset buffer serial untuk data berat
        if bleScale > 3 and flagSapa == 0:
            speak("Halooo! Selamat Datang di Anjungan Kesehatan Mandiri? Silahkan periksakan kesehatan anda")
            flagSapa = 1
            Gula = 0
            if bleScale < 3:
               flagSapa = 0 

        #######proses US
        serUS.reset_input_buffer()
        data_tinggi = serUS.read(7)  # Membaca 12 byte data
        if data_tinggi:
            Tinggi = parse_dataUS(data_tinggi)
            # Log data berat dan tinggi
            # Tinggi = Total
    
        # Proses data glukosa dari serESP
        if serESP.in_waiting > 0:
            #time.sleep(5)
            data2 = serESP.read(700)  # Membaca 700 byte data
            if data2:
                TotalESP = parse_dataESP(data2)
                print("\nData baru (sample):")
                print(TotalESP)

                # Pastikan TotalESP memiliki tepat 300 data sebelum melakukan prediksi
                if len(TotalESP) == 250:
                    TotalESP = np.array(TotalESP).reshape(1, -1)
                    #prediksi knn
                    Y_predict = knn.predict(TotalESP)
                    # Melakukan prediksi dengan model XGBoost
                    Y_pred_xgb = xgb_model.predict(TotalESP)
                    # Decode hasil prediksi XGBoost ke dalam kelas asli
                    Y_pred_xgb_decoded = label_encoder.inverse_transform(Y_pred_xgb)
                    print("\nData baru (sample):")
                    print(TotalESP)
                    print("\nHasil prediksi:")
                    print(Y_predict)
                    # Menampilkan hasil prediksi XGBoost yang sudah didecode
                    print("\nHasil prediksi XGBoost (setelah didecode):")
                    print(Y_pred_xgb_decoded)
                    Gula = (Y_pred_xgb_decoded[0]+Y_predict[0])/2
                    # print(type(TotalESP))
                    # print(TotalESP.shape)
                    # print(TotalESP[0])
                    conv = np.array(TotalESP[0],dtype=np.int64)
                    toStr = conv.astype(str)
                    glukosa = ','.join(toStr)
                    dataweb3 = {
                    "ins_time":current_time_str,
                    "glukosa": Gula
                    }
                    #response3 = requests.post(url3, json=dataweb3, headers=headers)
                    #if response3.status_code == 200:
                    #    print(f'data terkirim ke {url3}')
                    #    print(json.dumps(dataweb3, indent=1))
                    #else:
                    #    print(f'gagal kirim ke {url3}')

                else:
                    print(f"Jumlah data ESP tidak sesuai: {len(TotalESP)}")
                    # Tambahkan log atau penanganan kesalahan sesuai kebutuhan
                time.sleep(2)
            serESP.reset_input_buffer()

        # Kirim data ke web setiap 1000 iterasi
        dKirim = dKirim + 1 
        if dKirim > 7:
            dKirim = 0
            if kirim2 == 0:
                kirim2 = 1
                dataWeb = {
                    "id": "eec58e5e-cd44-319f-a1be-46dd38c5d01c",
                    "gula": round(Gula, 2),
                    "berat": bleScale,
                    "tinggi": round(Tinggi*1.031, 2)
                }
                response = requests.post(url, json=dataWeb, headers=headers)
                if response.status_code == 200:
                    print(f'Data berhasil terkirim ke {url}')
                    print(json.dumps(dataWeb, indent=4))
                else:
                    print(f'Gagal mengirim data')

                dataWeb2 = {
                    "id": "fe5110fa-4b69-3c21-acfa-4c5830af6b10",
                    "b_atas": bleSys,
                    "b_bawah": bleDias,
                    "denyut": bleBPM,
                }
                response2 = requests.post(url2, json=dataWeb2, headers=headers)
                if response2.status_code == 200:
                    print(f'Data berhasil terkirim ke {url2}')
                    print(json.dumps(dataWeb2, indent=4))
                else:
                    print(f'Gagal mengirim data: {dataWeb2}')
                
                
            else:
                kirim2 = 0

        # Log dan print status berat, tinggi, dan gula
        print(f"Gula: {Gula:.2f} | Berat: {bleScale} Kg | Tinggi: {Tinggi*1.031:.2f} cm | Tensi: {bleSys}/{bleDias} | Pulse: {bleBPM} bpm")

except KeyboardInterrupt:
    print("Program dihentikan oleh pengguna.")

except Exception as e:
    print(f'Terjadi error: {str(e)}')

finally:
    if serESP.is_open:
        serESP.close()
        print(f"Closed connection to {portESP}")
    if serUS.is_open:
        serUS.close()
        print(f"Closed connection to {portUS}")
