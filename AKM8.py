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


#setting
port = 'COM4'
portESP = 'COM6'
Total = [0,0]
flagSapa = 0
km = 0
dKirim = 0
Simpan = 0
dataSimpan = 0
Berat = 0
Tinggi = 0
Gula = 0

#################GLukonov train###########################
# Baca file Excel
file_path = 'data ADC Glukosa.xlsx'
sheet_name = 'Sheet1'
df = pd.read_excel(file_path, sheet_name=sheet_name)

# Membaca data dari sheet 1, mulai dari A2 ke EE300 untuk X
df_X = pd.read_excel(file_path, sheet_name='Sheet1', header=None, usecols="A:EE", skiprows=1, nrows=300)

# Mengambil nilai X dari DataFrame dan mengonversinya ke numpy array
X_train = df_X.to_numpy()
X_train = np.transpose(X_train)

# Membaca data dari sheet 1, mulai dari A1 ke EE1 untuk Y
df_Y = pd.read_excel(file_path, sheet_name='Sheet1', header=None, usecols="A:EE", nrows=1)

# Mengambil nilai Y dari DataFrame dan mengonversinya ke numpy array
Y_train = df_Y.to_numpy().flatten()

# Menampilkan dimensi X_train dan Y_train untuk memeriksa jumlah sampel
print("Dimensi X_train:", X_train.shape)
print("Dimensi Y_train:", Y_train.shape)

# Cetak X_train dan y_train untuk memeriksa
print("Data X_train (sample data):")
print(X_train)

print("\nData y_train (hasil):")
print(Y_train)

# Membuat model KNN
knn = KNeighborsClassifier(n_neighbors=2)  # Jumlah tetangga bisa disesuaikan

# Melatih model dengan data training
knn.fit(X_train, Y_train)
##########################################################

# URL API untuk mengirim data
url = ' https://kiosk.robotlintang.id/api/device'

# Data yang ingin Anda kirimkan dalam format JSON
dataWeb= {
    "id": "eec58e5e-cd44-319f-a1be-46dd38c5d01c",
    "gula": 36,
    "berat": f"{Berat:.2f}",
    "tinggi": f"{Tinggi:.2f}"
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

def speak(text):
    tts = gTTS(text=text, lang='id')
    tts.save("output.mp3")
    # Path ke ffplay
    ffplay_path = r'C:\ffmpeg\bin\ffplay.exe'
    #time.sleep(1)
    subprocess.run([ffplay_path, "-nodisp", "-autoexit", "output.mp3"], check=True)

def parse_data(data): 
    Beba = 0
    Tiba = 0
    Tot = [0,0]
    for k in range(len(data) - 6):
        if data[k] == 0xFF:
            Beba = data[k+1]+(data[k+2]/100)
            Tiba = data[k+3]+(data[k+4]/100)    
            Tot = [Beba,Tiba]
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
            
            # Proses 300 pasang 6-bit data yang diharapkan
            for j in range(300):
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
        ####BERAT DAN TINGGI#############
        ser.reset_input_buffer()
        data = ser.read(12)  # Membaca 60 byte data
        #print(f'{data}')
        if data:
            Total = parse_data(data)
        if Total[0] > 3 and flagSapa == 0:
            speak("Halooo! Selamat Datang di Anjungan Kesehatan Mandiri?")
            flagSapa = 1
        if Total[0] < 3:
            flagSapa = 0 
        km=km+1  
        if Simpan < Total[1]:
            Simpan = Total[1]
        if km>15:
            km = 0
            Tinggi = Simpan
            Berat = Total[0]
            Simpan = 0
        Berat = Total[0]
        ####GLUKOSA#############
        if serESP.in_waiting > 0:
            #serESP.reset_input_buffer()
            data2 = serESP.read(700)  # Membaca 60 byte data
            #print(f'{data}')
            if data2:
                TotalESP = parse_dataESP(data2)
                if len(TotalESP) == 300:
                    # Reshape data untuk prediksi
                    TotalESP = np.array(TotalESP).reshape(1, -1)
                    Y_pred = knn.predict(TotalESP)
                    # Menampilkan hasil prediksi
                    print("\nData baru (sample):")
                    print(TotalESP)

                    print("\nHasil prediksi:")
                    print(Y_pred)
                else:
                    print(f"Jumlah data ESP tidak sesuai: {len(TotalESP)}")
            serESP.reset_input_buffer()
               
        ################Kirim Data Web##########################
        dKirim = dKirim+1  
        if dKirim > 1000:
            dKirim = 0
            #web update
            dataWeb = {
                "id": "eec58e5e-cd44-319f-a1be-46dd38c5d01c",
                "gula": round(Gula, 2),
                "berat": round(Berat, 2),
                "tinggi": round(Tinggi, 2)
            }
            # Mengirimkan POST request dengan data JSON dan header yang sesuai
            response = requests.post(url, json=dataWeb, headers=headers)
            # Mengecek response status code
            if response.status_code == 200:
                print('Data berhasil terkirim')
                #print('Data yang dikirim:')
                print(json.dumps(dataWeb, indent=4))  # Cetak data dalam format JSON dengan indentasi
            else:
                print(f'Gagal mengirim data')
                #print(f'Status code: {response.status_code}')
            # Jeda waktu 5 detik sebelum mengirim data selanjutnya
            #time.sleep(5)
            #############################
        #######################################################
        print(f"Gula: {Gula:.2f} Berat: {Berat:.2f} Tinggi: {Tinggi:.2f}")

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
