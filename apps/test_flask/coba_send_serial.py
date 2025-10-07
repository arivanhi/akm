import serial
from flask import Flask
from flask_socketio import SocketIO

# --- KONFIGURASI ---
SERIAL_PORT = 'COM4'
BAUD_RATE = 9600
# -------------------

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
# Penting: Gunakan async_mode='eventlet'
socketio = SocketIO(app, async_mode='eventlet')

# Coba buka koneksi serial
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    print(f"Berhasil terhubung ke port serial: {SERIAL_PORT}")
except serial.SerialException as e:
    print(f"GAGAL terhubung ke port serial {SERIAL_PORT}: {e}")
    ser = None

def serial_reader_task():
    """Tugas yang akan dijalankan di background oleh SocketIO."""
    print(">>> Background task pembaca serial dimulai...")
    while True:
        if ser and ser.is_open:
            try:
                line = ser.readline().decode('utf-8', errors='ignore').rstrip()
                if line:
                    print(f"Data serial diterima: '{line}'")
                    # Kirim data ke semua klien yang terhubung
                    socketio.emit('serial_data', {'data': line})
            except Exception as e:
                print(f"Error di background task: {e}")
        # socketio.sleep() sangat penting agar server web tetap responsif
        socketio.sleep(0.1)

@app.route('/')
def index():
    # HTML-nya tetap sama seperti skrip tes sebelumnya
    return """
    <html>
    <head><title>Final Serial Test</title></head>
    <body>
        <h1>Final Serial Test</h1>
        <p>Buka Developer Console (F12) untuk melihat log WebSocket.</p>
        <h2>Data Diterima:</h2>
        <div id="log" style="border:1px solid black; padding: 5px; height: 300px; overflow-y: scroll;"></div>
        <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
        <script>
            var socket = io();
            var logDiv = document.getElementById('log');
            socket.on('serial_data', function(msg) {
                logDiv.innerHTML += msg.data + '<br>';
                logDiv.scrollTop = logDiv.scrollHeight;
            });
        </script>
    </body>
    </html>
    """

@socketio.on('connect')
def handle_connect():
    """Handler saat klien web terhubung."""
    print("Client web terhubung. Memulai background task jika belum berjalan.")
    # Cek apakah task sudah berjalan untuk menghindari duplikasi
    if not hasattr(g, 'serial_task_started'):
        socketio.start_background_task(target=serial_reader_task)
        g.serial_task_started = True

if __name__ == '__main__':
    if not ser:
        print("!!! PERINGATAN: Tidak bisa membuka port serial. Aplikasi berjalan tanpa pembacaan data.")
    
    print("Menjalankan server via Eventlet di http://0.0.0.0:5000")
    # Penting: Jalankan server melalui socketio.run()
    socketio.run(app, host='0.0.0.0', port=5000, )