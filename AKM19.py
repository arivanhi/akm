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
#from DFRobot_RaspberryPi_A02YYUW import DFRobot_A02_Distance as Board

# Setting
port = 'COM6'
portESP = 'COM7'
portUS = 'COM12'
portTensi = 'COM13'
kalt = 196
Total = 0
flagSapa = 0
km = 0
dKirim = 0
kirim2 = 0,
Simpan = 0
dataSimpan = 0
Berat = 0
Tinggi = 0
Gula = 0
tensionmax = 0
tensionmin = 0
tensiondenyut = 0
#tensi
LasthexSys = 0
LasthexDias = 0
LasthexBPM = 0

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

# Mengambil nilai Y dari DataFrame dan mengonversinya ke numpy array
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

##################################################
# URL API untuk mengirim data
url = 'https://kiosk.robotlintang.id/api/device'
url2 ='https://kiosk.robotlintang.id/api/tension'
# Data yang ingin Anda kirimkan dalam format JSON
dataWeb = {
    "id": "eec58e5e-cd44-319f-a1be-46dd38c5d01c",
    "gula": 36,
    "berat": f"{Berat:.2f}",
    "tinggi": f"{Tinggi:.2f}"
}
dataWeb2 = {
    "id": "fe5110fa-4b69-3c21-acfa-4c5830af6b10",
    "b_atas": 10,
    "b_bawah": 0.42,
    "denyut": 121
}

# Header sesuai dengan aturan yang diberikan
headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

try:
    # Membuka port serial
     ser = serial.Serial(port, 9600, timeout=1)
     print(f"Connected to {port} at 9600 baud rate.")
except serial.SerialException as e:
     print(f"Error opening or reading from serial port: {e}")
except KeyboardInterrupt:
     print("Exiting program.")

try:
    # Membuka port serial
    serESP = serial.Serial(portESP, 9600, timeout=1)
    print(f"Connected to {portESP} at 9600 baud rate.")
except serial.SerialException as e:
    print(f"Error opening or reading from serial port: {e}")
except KeyboardInterrupt:
    print("Exiting program.")

try:
    # Membuka port serial
    serUS = serial.Serial(portUS, 9600, timeout=1)
    print(f"Connected to {portUS} at 9600 baud rate.")
except serial.SerialException as e:
    print(f"Error opening or reading from serial port: {e}")
except KeyboardInterrupt:
    print("Exiting program.")

try:
    # Membuka port serial
    serTensi = serial.Serial(portTensi, 115200, timeout=1)
    print(f"Connected to {portTensi} at 9600 baud rate.")
except serial.SerialException as e:
    print(f"Error opening or reading from serial port: {e}")
except KeyboardInterrupt:
    print("Exiting program.")

def speak(text):
    tts = gTTS(text=text, lang='id')
    tts.save("output.mp3")
    ffplay_path = r'C:\ffmpeg\bin\ffplay.exe'
    subprocess.run([ffplay_path, "-nodisp", "-autoexit", "output.mp3"], check=True)

def parse_data(data):
    Beba = 0
    #Tiba = 0
    Tot = 0
    for k in range(len(data) - 6):
        if data[k] == 0xFF and data[k+1] == 0xFE :
            Beba = data[k+2] + (data[k+3] / 100)
            #Tiba = data[k+3] + (data[k+4] / 100)
            Tot = Beba
    return Tot

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

try:
    while True:
        # Reset buffer serial untuk data berat
        ser.reset_input_buffer()
        data = ser.read(12)  # Membaca 12 byte data
        if data:
            Total = parse_data(data)
            # Log data berat dan tinggi
            if Total > 3 and flagSapa == 0:
               speak("Halooo! Selamat Datang di Anjungan Kesehatan Mandiri? Silahkan periksakan kesehatan anda")
               flagSapa = 1
               Gula = 0
               tesionmax = 0
               tensionmin = 0
               tensiondenyut = 0
               LasthexSys = 0
               LasthexDias = 0
               LasthexBPM = 0
            if Total < 3:
               flagSapa = 0 
            Berat = Total
        #######proses US
        serUS.reset_input_buffer()
        data = serUS.read(7)  # Membaca 12 byte data
        if data:
            Total = parse_dataUS(data)
            # Log data berat dan tinggi
            Tinggi = Total
        ############proses tensi
        buff = bytearray(5)
        final_buff = bytearray(11)

        b_read = 0
        j = 0
        b_discard = 0
        i = 0
        end = 0

        while serTensi.in_waiting:
            if b_read == 0:
                buff[0] = serTensi.read(1)[0]
                if buff[0] == ord('e'):
                    buff[1] = serTensi.read(1)[0]
                    if buff[1] == ord('r'):
                        buff[2] = serTensi.read(1)[0]
                        if buff[2] == ord('r'):
                            buff[3] = serTensi.read(1)[0]
                            if buff[3] == ord(':'):
                                buff[4] = serTensi.read(1)[0]
                                if buff[4] == ord('0'):
                                    b_read = 1
                                    j = 0
                                    b_discard = 0
                                    i = 0

            if b_read:
                if b_discard == 0:
                    discard = serTensi.read(1)[0]
                    i += 1
                elif j < 11:
                    final_buff[j] = serTensi.read(1)[0]
                    j += 1
                else:
                    b_read = 0

                if i == 30:
                    b_discard = 1

            time.sleep(0.002)
            end += 1
            if end > 1000:
                break

        if final_buff[0] > ord('9'):
            hexSys = (final_buff[0] - ord('7')) * 16
        else:
            hexSys = (final_buff[0] - ord('0')) * 16

        if final_buff[1] > ord('9'):
            hexSys += (final_buff[1] - ord('7'))
        else:
            hexSys += (final_buff[1] - ord('0'))

        if final_buff[3] > ord('9'):
            hexDias = (final_buff[3] - ord('7')) * 16
        else:
            hexDias = (final_buff[3] - ord('0')) * 16

        if final_buff[4] > ord('9'):
            hexDias += (final_buff[4] - ord('7'))
        else:
            hexDias += (final_buff[4] - ord('0'))

        if final_buff[9] > ord('9'):
            hexBPM = (final_buff[9] - ord('7')) * 16
        else:
            hexBPM = (final_buff[9] - ord('0')) * 16

        if final_buff[10] > ord('9'):
            hexBPM += (final_buff[10] - ord('7'))
        else:
            hexBPM += (final_buff[10] - ord('0'))
        if hexBPM != -816:
            LasthexSys = hexSys
            LasthexDias = hexDias
            LasthexBPM = hexBPM
        tensionmax = LasthexSys
        tensionmin = LasthexDias
        tensiondenyut = LasthexBPM
        #print(LasthexSys)
        #print(LasthexDias)
        #print(LasthexBPM)
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
                    "berat": round(Berat, 2),
                    "tinggi": round(Tinggi, 2)
                }
                response = requests.post(url, json=dataWeb, headers=headers)
                if response.status_code == 200:
                    print('Data berhasil terkirim')
                    print(json.dumps(dataWeb, indent=4))
                else:
                    print(f'Gagal mengirim data')
            else:
                kirim2 = 0
                dataWeb2 = {
                    "id": "fe5110fa-4b69-3c21-acfa-4c5830af6b10",
                    "b_atas": round(tensionmax, 2),
                    "b_bawah": round(tensionmin, 2),
                    "denyut": round(tensiondenyut, 2),
                }
                response = requests.post(url2, json=dataWeb2, headers=headers)
                if response.status_code == 200:
                    print('Data berhasil terkirim')
                    print(json.dumps(dataWeb2, indent=4))
                else:
                    print(f'Gagal mengirim data: {dataWeb2}')

        # Log dan print status berat, tinggi, dan gula
        print(f"Gula: {Gula:.2f} Berat: {Berat:.2f} Tinggi: {Tinggi:.2f} Tensi: {tensionmax:.2f} / {tensionmin:.2f} Pulse: {tensiondenyut:.2f}")

except KeyboardInterrupt:
    print("Program dihentikan oleh pengguna.")

except Exception as e:
    print(f'Terjadi error: {str(e)}')

finally:
    if ser.is_open:
        ser.close()
        print(f"Closed connection to {port}.")
    if serESP.is_open:
        serESP.close()
        print(f"Closed connection to {portESP}")
    if serUS.is_open:
        serUS.close()
        print(f"Closed connection to {portUS}")
    if serTensi.is_open:
        serTensi.close()
        print(f"Closed connection to {portTensi}")
