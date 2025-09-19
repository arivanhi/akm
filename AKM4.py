import time
from gtts import gTTS
from pydub import AudioSegment
from pydub.playback import play
import serial
import subprocess
import requests
import json

#setting
port = 'COM4'
Total = [0,0]
flagSapa = 0
km = 0
Simpan = 0
dataSimpan = 0
Berat = 0
Tinggi = 0

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

def speak(text):
    tts = gTTS(text=text, lang='id')
    tts.save("output.mp3")
    # Path ke ffplay
    ffplay_path = r'C:\ffmpeg\bin\ffplay.exe'
    #time.sleep(1)
    subprocess.run([ffplay_path, "-nodisp", "-autoexit", "output.mp3"], check=True)

def parse_data(data, ser): 
    Beba = 0
    Tiba = 0
    Tot = [0,0]
    for k in range(len(data) - 6):
        if data[k] == 0xFF:
            Beba = data[k+1]+(data[k+2]/100)
            Tiba = data[k+3]+(data[k+4]/100)    
            Tot = [Beba,Tiba]
    return Tot

try:
    while True:
        ser.reset_input_buffer()
        data = ser.read(12)  # Membaca 60 byte data
        #print(f'{data}')
        if data:
            Total = parse_data(data, ser)
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
            #web update
            dataWeb = {
                "id": "eec58e5e-cd44-319f-a1be-46dd38c5d01c",
                "gula": 36.45,
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
        Berat = Total[0]
        print(f"Berat: {Berat:.2f} Tinggi: {Tinggi:.2f}")

except KeyboardInterrupt:
    print("Program dihentikan oleh pengguna.")

except Exception as e:
    print(f'Terjadi error: {str(e)}')

finally:
    if ser.is_open:
        ser.close()
        print(f"Closed connection to {port}.")
