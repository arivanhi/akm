import time
from gtts import gTTS
from pydub import AudioSegment
from pydub.playback import play
import io
import serial

#setting
port = 'COM3'
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
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        song = AudioSegment.from_file(fp, format="mp3")
        play(song)

try:
    while True:
        ser.reset_input_buffer()
        data = ser.read(60)  # Membaca 12 byte data
        print(f'{data}')
        speak("Halooo! Selamat Datang di Anjungan Kesehatan Mandiri?")
        
except KeyboardInterrupt:
    print("Program dihentikan oleh pengguna.")

finally:
    if ser.is_open:
            ser.close()
            print(f"Closed connection to {port}.")