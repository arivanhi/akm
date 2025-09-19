import time
from gtts import gTTS
from pydub import AudioSegment
from pydub.playback import play
import io
import serial
import subprocess

#setting
port = 'COM3'
Berat = 0
flagSapa = 0
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
    Bebi = 0
    for k in range(len(data) - 10):
        if data[k] == 0xFF:
            Bebi = data[k+1]+(data[k+2]/100)    
    return Bebi

try:
    while True:
        ser.reset_input_buffer()
        data = ser.read(60)  # Membaca 60 byte data
        #print(f'{data}')
        if data:
            Berat = parse_data(data, ser)
        if Berat > 3 and flagSapa == 0:
            speak("HaaHalooo! Selamat Datang di Anjungan Kesehatan Mandiri?")
            flagSapa = 1
        if Berat < 3:
            flagSapa = 0 
        print("Berat:", Berat)

except KeyboardInterrupt:
    print("Program dihentikan oleh pengguna.")

finally:
    if ser.is_open:
        ser.close()
        print(f"Closed connection to {port}.")
