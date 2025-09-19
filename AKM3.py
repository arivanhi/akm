import time
from gtts import gTTS
from pydub import AudioSegment
from pydub.playback import play
import io
import serial
import subprocess

#setting
port = 'COM4'
Total = [0,0]
flagSapa = 0
km = 0
Simpan = 0
dataSimpan = 0
Berat = 0
Tinggi = 0
#Menghubungkan ke board Arduino
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
    for k in range(len(data) - 10):
        if data[k] == 0xFF:
            Beba = data[k+1]+(data[k+2]/100)
            Tiba = data[k+3]+(data[k+4]/100)    
            Tot = [Beba,Tiba]
    return Tot

try:
    while True:
        ser.reset_input_buffer()
        data = ser.read(60)  # Membaca 60 byte data
        #print(f'{data}')
        if data:
            Total = parse_data(data, ser)
        if Total[0] > 3 and flagSapa == 0:
            speak("HaaHalooo! Selamat Datang di Anjungan Kesehatan Mandiri?")
            flagSapa = 1
        if Total[0] < 3:
            flagSapa = 0 
        km=km+1  
        if Simpan < Total[1]:
            Simpan = Total[1]
        if km>15:
            km = 0
            Tinggi = Simpan
            Simpan = 0
        Berat = Total[0]
        print(f"Berat: {Berat:.2f} Tinggi: {Tinggi:.2f}")

except KeyboardInterrupt:
    print("Program dihentikan oleh pengguna.")

finally:
    if ser.is_open:
        ser.close()
        print(f"Closed connection to {port}.")
