import os
import io
import csv
import psycopg2
from psycopg2.extras import RealDictCursor
import bcrypt
import asyncio
import json
from flask import Flask, render_template, request, redirect, url_for, flash, session, g, jsonify, Response
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
import requests
import xgboost as xgb
import numpy as np
from sklearn.preprocessing import LabelEncoder
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import confusion_matrix, accuracy_score
import joblib
import subprocess
from escpos.printer import Serial, Usb


# Muat environment variables dari file .env
load_dotenv()

MQTT_BROKER_HOST = os.getenv('MQTT_BROKER_HOST', 'localhost')
MQTT_DATA_TOPIC = "akm/data"
MQTT_COMMAND_TOPIC = "akm/command"
MQTT_PREDICTION_TOPIC = "akm/prediction_data"
MQTT_RESULT_TOPIC = "akm/prediction_result"
MQTT_PROGRESS_TOPIC = "akm/progress" 

# PRINTER_MAC = "5A:4A:FA:C1:6E:D0"  # <--- ISI MAC ADDRESS PRINTER
# PORT = '/dev/rfcomm0'
# BAUDRATE = 9600

# --- Konfigurasi Aplikasi Flask ---
app = Flask(__name__)
@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT id, username, role FROM users WHERE id = %s', (user_id,))
        g.user = cur.fetchone() # g.user sekarang berisi tuple (id, username, role)
        cur.close()
        conn.close()
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24).hex())
socketio = SocketIO(app, async_mode='threading')
active_patient_id = None # Variabel global untuk melacak pasien aktif
active_patient_name = None
print("Memuat model Machine Learning...")
models_xgb = {}
models_knn = {}

try:
    # --- 1. ASAM URAT (120 Fitur) ---
    models_xgb['asam_urat'] = xgb.XGBRegressor()
    models_xgb['asam_urat'].load_model('model/xgboost_asam_urat_regressor.json')
    models_knn['asam_urat'] = joblib.load('model/knn_asam_urat_regressor.pkl')
    print("-> Model Asam Urat dimuat.")

    # --- 2. KOLESTEROL (20 Fitur) ---
    models_xgb['cholesterol'] = xgb.XGBRegressor()
    models_xgb['cholesterol'].load_model('model/xgboost_kolesterol_regressor.json')
    models_knn['cholesterol'] = joblib.load('model/knn_kolesterol_regressor.pkl')
    print("-> Model Kolesterol dimuat.")

    # --- 3. GULA DARAH (250 Fitur) ---
    models_xgb['gula_darah'] = xgb.XGBRegressor()
    models_xgb['gula_darah'].load_model('model/xgboost_glukosa_regressor.json')
    models_knn['gula_darah'] = joblib.load('model/knn_glukosa_regressor.pkl')
    print("-> Model Gula Darah dimuat.")

except Exception as e:
    print(f"!!! ERROR memuat model: {e}")
    print("Pastikan Anda sudah menjalankan script 'train_..._regression.py' untuk semua tipe.")

# =================================================================
def setup_bluetooth_connection():
    """
    Fungsi ini akan memaksa binding rfcomm0 sebelum mencetak.
    Solusi anti-gagal jika keyboard mengambil alih koneksi.
    """
    print("Memeriksa koneksi printer...")
    
    # 1. Cek apakah port sudah ada
    if not os.path.exists(PORT):
        print(f"Port {PORT} tidak ditemukan. Mencoba binding ulang...")
        
        # Jalankan perintah rfcomm bind via terminal command
        # Kita gunakan 'sudo' di dalam command, pastikan user pi bisa sudo tanpa password
        # atau jalankan script ini dengan 'sudo python ...'
        cmd = f"rfcomm bind 0 {PRINTER_MAC} 1" # Angka 1 adalah channel (biasanya 1)
        
        try:
            subprocess.run(cmd, shell=True, check=True)
            print("Binding perintah dikirim. Menunggu 3 detik...")
            time.sleep(3) # Tunggu sebentar agar port terbentuk
        except subprocess.CalledProcessError:
            print("Gagal melakukan binding. Pastikan MAC Address benar.")
            return False
            
    # 2. Cek lagi setelah binding
    if os.path.exists(PORT):
        print("Koneksi Bluetooth Printer Siap!")
        return True
    else:
        print("Gagal terhubung ke printer.")
        return False
# --- FUNGSI BANTUAN: PREPROCESSING DATA ---
def preprocess_sensor_data(data_list, target_length, needs_conversion=False):
    """
    Mengubah list mentah menjadi numpy array siap prediksi:
    1. Konversi 12-bit ke 8-bit (jika perlu)
    2. Padding/Truncating ke target_length
    3. Reshape ke (1, target_length)
    """
    # 1. Konversi ke Numpy Array
    data_np = np.array(data_list)
    
    # 2. Konversi 12-bit ke 8-bit (Khusus Glukosa)
    if needs_conversion:
        # Rumus: (nilai / 4095) * 255
        data_np = (data_np / 4095.0) * 255.0
    
    # Bulatkan ke integer
    data_np = np.round(data_np).astype(int)

    # 3. Sesuaikan Panjang Data (Padding/Cutting)
    current_len = len(data_np)
    if current_len < target_length:
        # Kurang: Tambahkan 0 di belakang
        padding = np.zeros(target_length - current_len, dtype=int)
        data_np = np.concatenate((data_np, padding))
    elif current_len > target_length:
        # Lebih: Potong data
        data_np = data_np[:target_length]

    # 4. Reshape untuk input model (1 baris, N kolom)
    return data_np.reshape(1, -1)

# --- Fungsi-fungsi Bantuan & Middleware (Tidak Berubah) ---
# --- Logika MQTT Client ---
def on_connect(client, userdata, flags, rc):
    print(f"Terhubung ke MQTT Broker dengan hasil: {rc}")
    client.subscribe(MQTT_DATA_TOPIC)
    client.subscribe(MQTT_PREDICTION_TOPIC)
    client.subscribe(MQTT_RESULT_TOPIC)
    client.subscribe(MQTT_PROGRESS_TOPIC)
    print(f"Subscribe ke topik: {MQTT_DATA_TOPIC}, {MQTT_RESULT_TOPIC}, {MQTT_PROGRESS_TOPIC} dan {MQTT_PREDICTION_TOPIC}")

def on_message(client, userdata, msg):
    payload_str = msg.payload.decode('utf-8')
    print(f"Data diterima dari MQTT topik '{msg.topic}': {payload_str}")

    # --- KASUS 1: TERIMA DATA ARRAY UNTUK PREDIKSI ---
    if msg.topic == MQTT_PREDICTION_TOPIC:
        print(f"Menerima data array untuk prediksi...")
        try:
            sensor_package = json.loads(payload_str)
            data_type = sensor_package.get('type')
            sensor_data = sensor_package.get('data')
            
            if data_type == 'tensi':
                raw_sys = str(sensor_package.get('sys', '0'))
                raw_dia = str(sensor_package.get('dia', '0'))
                raw_pulse = str(sensor_package.get('pulse', '0'))

                # Bersihkan spasi/enter
                clean_sys = raw_sys.strip()
                clean_dia = raw_dia.strip()
                clean_pulse = raw_pulse.strip()

                print(f"Mengirim Tensi ke Web -> Sys:{clean_sys}, Dia:{clean_dia}, Pulse:{clean_pulse}")

                # Kirim data BERSIH ke Frontend
                socketio.emit('measurement_update', {
                    'type': 'tensi',
                    'sys': clean_sys,
                    'dia': clean_dia,
                    'pulse': clean_pulse
                })
                print("Data Tensi dikirim ke Frontend.")
                
                # JANGAN LANJUT KE BAWAH (ML PREDICTION)
                return

            if not sensor_data or not data_type: return
            
            # --- KONFIGURASI SPESIFIK TIPE ---
            target_length = 0
            needs_conversion = False
            
            
            if data_type == 'gula_darah':
                target_length = 250
                needs_conversion = False # Aktifkan konversi 12-bit ke 8-bit
            elif data_type == 'asam_urat':
                target_length = 120
            elif data_type == 'cholesterol':
                target_length = 20

            # --- PROSES DATA ---
            data_input = preprocess_sensor_data(sensor_data, target_length, needs_conversion)
            
            # Hitung rata-rata untuk info tambahan (dari data yang sudah diproses)
            numeric_value = round(np.mean(data_input), 2)
            
            hasil_akhir = 0.0

            # --- LAKUKAN PREDIKSI ---
            if data_type in models_xgb and data_type in models_knn:
                # Prediksi XGBoost
                pred_xgb = models_xgb[data_type].predict(data_input)[0]
                
                # Prediksi KNN (menggunakan model .pkl, BUKAN array .npy)
                pred_knn = models_knn[data_type].predict(data_input)[0]
                
                # Ensemble (Rata-rata)
                hasil_akhir = (pred_xgb + pred_knn) / 2
                
                print(f"Prediksi {data_type} -> XGB: {pred_xgb:.2f}, KNN: {pred_knn:.2f}, Avg: {hasil_akhir:.2f}")
            else:
                print(f"Model untuk {data_type} belum dimuat.")
                return

            # --- KIRIM HASIL KE TOPIK RESULT (Agar thread-safe) ---
            result_payload = {
                'type': data_type,
                'value': float(hasil_akhir),
                # 'numeric_value': float(numeric_value)
            }
            client.publish(MQTT_RESULT_TOPIC, json.dumps(result_payload))
            if active_patient_id:
                try:
                    # Kita buka koneksi sebentar khusus untuk simpan ini
                    conn_raw = get_db_connection()
                    cur_raw = conn_raw.cursor()

                    # Simpan array sebagai JSON
                    cur_raw.execute("""
                        INSERT INTO raw_sensor_data (patient_id, patient_name, measurement_type, raw_data, prediction_result)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (active_patient_id, active_patient_name, data_type, json.dumps(sensor_data), float(hasil_akhir)))

                    conn_raw.commit()
                    cur_raw.close()
                    conn_raw.close()
                    print(f"Data mentah {data_type} untuk Pasien {active_patient_id} berhasil disimpan.")
                except Exception as db_err:
                    print(f"Gagal menyimpan data mentah: {db_err}")

        except Exception as e:
            print(f"Gagal memproses data prediksi: {e}")
            import traceback
            traceback.print_exc()

    # --- KASUS 2: TERIMA HASIL PREDIKSI (DARI DIRI SENDIRI) ---
    elif msg.topic == MQTT_RESULT_TOPIC:
        try:
            result_data = json.loads(payload_str)
            # Teruskan ke browser
            socketio.emit('prediction_result', result_data)
        except Exception as e:
            print(f"Error forward result: {e}")

    # --- KASUS 3: DATA REAL-TIME & PROGRES ---
    elif msg.topic == "akm/progress":
        try:
            socketio.emit('measurement_progress', json.loads(payload_str))
        except: pass
        
    elif msg.topic == MQTT_DATA_TOPIC:
        # Logika data mentah (Stop / Angka)
        parts = payload_str.split(':')
        if len(parts) == 2:
            tipe, nilai_str = parts[0].strip(), parts[1].strip()
            # Cek STOP
            if nilai_str.upper() == 'STOP':
                 # Kirim sinyal stop (opsional, krn biasanya dipicu prediction_result)
                 pass
            else:
                try:
                    val = float(nilai_str)
                    socketio.emit('measurement_update', {'type': tipe, 'value': val})
                except: pass

# Inisialisasi MQTT Client
mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(MQTT_BROKER_HOST, 1883, 60)
mqtt_client.loop_start() # Menjalankan client di background thread
# Fungsi untuk membuat koneksi ke database
def get_db_connection():
    conn = psycopg2.connect(
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST'),  
        port=os.getenv('DB_PORT')
    )
    return conn

# Fungsi untuk membuat user admin jika belum ada
def create_default_admin():
    conn = get_db_connection()
    cur = conn.cursor()
    # Cek apakah user 'admin' sudah ada
    cur.execute("SELECT 1 FROM users WHERE username = 'admin'")
    if cur.fetchone() is None:
        print("Membuat user admin default...")
        # Hash password default untuk admin
        # PENTING: Password ini harus diganti di production!
        default_password = b'admin123'
        hashed_password = bcrypt.hashpw(default_password, bcrypt.gensalt())
        
        cur.execute(
            """
            INSERT INTO users (nama, username, email, no_hp, password_hash, role, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            ('Admin Utama', 'admin', 'admin@example.com', '081234567890', hashed_password.decode('utf-8'), 'admin', True)
        )
        conn.commit()
        print("User admin berhasil dibuat.")
    else:
        print("User admin sudah ada.")
    cur.close()
    conn.close()

# --- Routes & API Endpoints (Tidak Berubah) ---
# (Semua @app.route Anda dari kode sebelumnya diletakkan di sini)
# Contoh:
@app.route('/')
def index():
    return redirect(url_for('login'))

# Route untuk halaman login
@app.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password'].encode('utf-8')

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cur.fetchone() # user[0] = id, user[5] = password_hash, user[6] = role
        cur.close()
        conn.close()

        if user and bcrypt.checkpw(password, user[5].encode('utf-8')):
            session['user_id'] = user[0] # Simpan ID user ke dalam session
            session['user_role'] = user[6] # Simpan role user ke dalam session
            flash(f'Selamat datang, {user[1]}!', 'success') # user[1] adalah username
            return redirect(url_for('dashboard'))
        else:
            flash('Username atau Password salah. Silakan coba lagi.', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear() # Hapus semua data dari session
    flash('Anda telah keluar.', 'info')
    return redirect(url_for('login'))

# TAMBAHKAN route baru ini di bawah fungsi login
@app.route('/dashboard')
def dashboard():
    if g.user is None: # Jika belum login, redirect ke login
        flash('Anda perlu login untuk mengakses dashboard.', 'warning')
        return redirect(url_for('login'))

    # Kirim data user ke template dashboard
    return render_template('dashboard.html', user_data=g.user)

# Route untuk halaman sign up (pendaftaran)
@app.route('/signup', methods=('GET', 'POST'))
def signup():
    if request.method == 'POST':
        # Ambil data dari form
        nama = request.form['nama']
        username = request.form['username']
        email = request.form['email']
        no_hp = request.form['no_hp']
        password = request.form['password'].encode('utf-8') # encode ke bytes
        confirm_password = request.form['confirm_password'].encode('utf-8')
        role = request.form['role']

        # Validasi sederhana
        if password != confirm_password:
            flash('Password dan konfirmasi password tidak cocok!', 'danger')
            return redirect(url_for('signup'))

        # Hash password sebelum disimpan
        hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            # Masukkan data ke database
            cur.execute(
                """
                INSERT INTO users (nama, username, email, no_hp, password_hash, role)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (nama, username, email, no_hp, hashed_password.decode('utf-8'), role)
            )
            conn.commit()
            flash('Pendaftaran berhasil! Silakan tunggu aktivasi dari admin atau via email.', 'success')
            return redirect(url_for('login'))
        except psycopg2.IntegrityError:
            # Tangani jika username atau email sudah ada
            conn.rollback() # Batalkan transaksi
            flash('Username atau Email sudah terdaftar.', 'danger')
        finally:
            # Selalu tutup koneksi
            cur.close()
            conn.close()

    return render_template('signup.html')

@app.route('/measure', methods=('GET', 'POST'))
def measure():
    if g.user is None:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Logika ini sekarang untuk AJAX


        conn = get_db_connection()
        cur = conn.cursor()
        try:
    # Ambil semua data dari form
            nama_lengkap = request.form['nama_pasien']
            jenis_kelamin = request.form.get('jenis_kelamin')
            alamat = request.form['alamat']
            umur = request.form['umur']
            nik = request.form['nik']
            no_hp = request.form['no_hp']

            # Perintah SQL dengan semua kolom dan placeholder yang benar
            cur.execute(
                """
                INSERT INTO patients (nama_lengkap, jenis_kelamin, alamat, umur, nik, no_hp)
                VALUES (%s, %s, %s, %s, %s, %s) 
                RETURNING id, nama_lengkap, nik, alamat, umur, jenis_kelamin
                """,
                (nama_lengkap, jenis_kelamin, alamat, umur, nik, no_hp)
            )
            new_patient = cur.fetchone()
            conn.commit()
            return jsonify({
                'status': 'success',
                'message': 'Pasien baru berhasil didaftarkan!',
                'patient': {
                    'id': new_patient[0],
                    'nama': new_patient[1],
                    'nik': new_patient[2],
                    'alamat': new_patient[3],
                    'umur': new_patient[4],         # <-- TAMBAHAN
                    'jenis_kelamin': new_patient[5] # <-- TAMBAHAN
                }
            })
        except psycopg2.IntegrityError:
            conn.rollback()
            return jsonify({'status': 'error', 'message': 'NIK sudah terdaftar. Gunakan fitur pasien lama.'}), 400
        finally:
            cur.close()
            conn.close()

    return render_template('measure.html')

@app.route('/api/print_receipt', methods=['POST'])
def print_receipt():
    if g.user is None:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    data = request.json
    
    try:
        # Koneksi ke Printer via RFCOMM0
        # Baudrate 9600 biasanya standar untuk EPPOS
        # p = Serial(devfile=PORT, baudrate=BAUDRATE, bytesize=8, parity='N', stopbits=1, timeout=1.00, dsrdtr=True)
        p = Usb(0x0416, 0x5011, 0, 0x81, 0x03)

        # --- FORMAT STRUK ---
        p.set(align='center')
        p.text("Hasil Pemeriksaan Kesehatan\n")
        p.text("================================\n")
        
        p.set(align='left')
        p.text(f"Nama    : {data.get('nama')}\n")
        p.text(f"Tanggal : {data.get('tanggal')}\n")
        p.text("--------------------------------\n")

        results = data.get('hasil', [])
        for res in results:
            tipe = res['tipe']
            nilai = res['nilai']
            status = res['status']
            
            p.set(bold=True)
            p.text(f"{tipe}\n")
            p.set(bold=False)
            p.text(f"Nilai  : {nilai}\n")
            p.text(f"Status : {status}\n")
            

        p.set(align='center')
        p.text("- - - - - - - - - - - - - - - - \n")
        p.text("Terima Kasih\n")
        p.text("Semoga Sehat Selalu\n")
        p.text("\n\n\n") # Feed kertas ke bawah
        
        # PENTING: Tutup koneksi agar tidak lock
        p.close() 

        return jsonify({'status': 'success', 'message': 'Struk berhasil dicetak!'})

    except Exception as e:
        print(f"Error Printer: {e}")
        return jsonify({'status': 'error', 'message': 'Gagal mencetak. Cek koneksi printer.'}), 500

@app.route('/upload_data', methods=['POST'])
def upload_data():
    """Mengambil semua data pengukuran, format ke JSON, dan kirim ke server eksternal."""
    if g.user is None:
        return jsonify({'status': 'error', 'message': 'Akses ditolak'}), 401
    
    # 1. Ambil semua data dari database
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            p.nama_lengkap, p.nik, p.umur, p.jenis_kelamin,
            m.measured_at, m.cholesterol_value, m.uric_acid_value, m.blood_sugar_value
        FROM measurements m
        JOIN patients p ON m.patient_id = p.id
        ORDER BY m.measured_at;
    """)
    all_data = cur.fetchall()
    cur.close()
    conn.close()

    if not all_data:
        return jsonify({'status': 'error', 'message': 'Tidak ada data untuk diunggah.'}), 404

    # 2. Konversi data ke format JSON (list of dictionaries)
    payload = []
    for row in all_data:
        payload.append({
            "nama_pasien": row[0],
            "nik": row[1],
            "umur": row[2],
            "jenis_kelamin": row[3],
            "tanggal_pengukuran": row[4].isoformat(),
            "kolesterol": row[5],
            "asam_urat": row[6],
            "gula_darah": row[7]
        })

    # 3. Kirim data ke API eksternal
    external_api_url = os.getenv('EXTERNAL_API_URL')
    if not external_api_url:
        return jsonify({'status': 'error', 'message': 'URL API eksternal tidak diatur.'}), 500

    try:
        response = requests.post(external_api_url, json=payload, timeout=30) # Timeout 30 detik
        response.raise_for_status()  # Ini akan raise error jika status code bukan 2xx

        return jsonify({'status': 'success', 'message': f'Berhasil mengunggah {len(payload)} data pengukuran!'})

    except requests.exceptions.RequestException as e:
        print(f"Gagal mengunggah data: {e}")
        return jsonify({'status': 'error', 'message': 'Gagal terhubung ke server eksternal.'}), 500


# --- HANDLER UNTUK WEBSOCKETS ---

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('start_measurement')
def handle_start_measurement(data):
    """Menerima flag dari web dan mengirimkannya ke Node-RED via MQTT."""
    global active_patient_id, active_patient_name
    flag = data.get('flag')
    active_patient_id = data.get('patient_id')
    active_patient_name = data.get('patient_name')
    print(f"Memulai pengukuran untuk: {active_patient_name} Pasien ID: {active_patient_id}, Flag: {flag}")
    print(f"Mengirim flag '{flag}' ke topik {MQTT_COMMAND_TOPIC}")
    mqtt_client.publish(MQTT_COMMAND_TOPIC, str(flag))
    

@socketio.on('save_session_data')
def handle_save_session(data):
    patient_id = data.get('patient_id')
    results = data.get('results')
    user_id = session.get('user_id') # Ambil ID operator yang sedang login

    if not all([patient_id, results, user_id]):
        emit('save_status', {'status': 'error', 'message': 'Data tidak lengkap.'})
        return

    cholesterol = results.get('cholesterol', 0.0)
    uric_acid = results.get('asam_urat', 0.0)
    blood_sugar = results.get('gula_darah', 0.0)
    tensi_data = results.get('tensi')
    if isinstance(tensi_data, dict):
        bp_sys = int(tensi_data.get('sys', 0))
        bp_dia = int(tensi_data.get('dia', 0))
        bp_pulse = int(tensi_data.get('pulse', 0))
    else:
        # Jika data tensi belum ada/kosong
        bp_sys = 0
        bp_dia = 0
        bp_pulse = 0

    # Fisik (Manual Input)
    height = float(results.get('tinggi_badan', 0.0))
    weight = float(results.get('berat_badan', 0.0))

    # --- 2. SIMPAN KE DATABASE ---
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO measurements (
                patient_id, user_id, 
                cholesterol_value, uric_acid_value, blood_sugar_value, 
                blood_pressure_sys, blood_pressure_dia, blood_pressure_pulse,
                height, weight,
                measured_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """,
            (
                patient_id, user_id,
                cholesterol, uric_acid, blood_sugar,
                bp_sys, bp_dia, bp_pulse,
                height, weight
            )
        )
        conn.commit()
        print(f"Data pengukuran untuk pasien ID {patient_id} berhasil disimpan.")
        emit('save_status', {'status': 'success', 'message': 'Data berhasil disimpan!'})
    except Exception as e:
        conn.rollback()
        print(f"Gagal menyimpan data pengukuran: {e}")
        emit('save_status', {'status': 'error', 'message': 'Terjadi kesalahan saat menyimpan data.'})
    finally:
        cur.close()
        conn.close()

@app.route('/api/search_patients')
def search_patients():
    if g.user is None:
        return jsonify([]) # Return empty jika belum login

    query = request.args.get('q', '')
    conn = get_db_connection()
    cur = conn.cursor()
    # Cari pasien yang namanya mengandung query, limit 5 hasil
    cur.execute(
        "SELECT id, nama_lengkap, nik, alamat, umur, jenis_kelamin FROM patients WHERE nama_lengkap ILIKE %s LIMIT 5",
        (f'%{query}%',)
    )
    patients = [{
        'id': row[0], 'nama': row[1], 'nik': row[2], 'alamat': row[3],
        'umur': row[4], 'jenis_kelamin': row[5] # <-- TAMBAHAN
    } for row in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(patients)

@app.route('/data_pengukuran')
def data_pengukuran():
    if g.user is None:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    # Query ini menggabungkan tabel pasien dan pengukuran untuk mendapatkan
    # nama pasien dan tanggal pengukuran TERBARU untuk setiap pasien.
    cur.execute("""
        SELECT p.id, p.nama_lengkap, MAX(m.measured_at) as last_measured
        FROM patients p
        JOIN measurements m ON p.id = m.patient_id
        GROUP BY p.id, p.nama_lengkap
        ORDER BY last_measured DESC;
    """)
    patients_with_dates = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('data_pengukuran.html', patients=patients_with_dates)

@app.route('/api/patient_history/<int:patient_id>')
def api_patient_history(patient_id):
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # Query Dasar
    query = """
        SELECT 
            id, 
            measured_at, 
            cholesterol_value, 
            uric_acid_value, 
            blood_sugar_value,
            blood_pressure_sys, 
            blood_pressure_dia, 
            height, 
            weight
        FROM measurements
        WHERE patient_id = %s
    """
    params = [patient_id]

    # Filter Tanggal (Opsional)
    if start_date and end_date:
        query += " AND measured_at BETWEEN %s AND %s"
        params.extend([start_date, end_date])
    
    query += " ORDER BY measured_at DESC"

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor) # Gunakan RealDictCursor agar hasil jadi JSON
    cur.execute(query, tuple(params))
    history = cur.fetchall()
    
    cur.close()
    conn.close()

    # Format Tanggal agar enak dibaca di JS
    for record in history:
        if record['measured_at']:
            record['formatted_date'] = record['measured_at'].strftime('%d-%m-%Y %H:%M')
            record['raw_date'] = record['measured_at'].strftime('%Y-%m-%d') # Untuk filter JS

    return jsonify({'status': 'success', 'data': history})

@app.route('/api/patient_measurements/<int:patient_id>')
def get_patient_measurements(patient_id):
    if g.user is None:
        return jsonify({'error': 'Unauthorized'}), 401

    # Ambil parameter filter dari URL
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    conn = get_db_connection()
    cur = conn.cursor()

    # ==========================================
    # 1. AMBIL BIODATA
    # ==========================================
    query_bio = "SELECT nama_lengkap, umur, jenis_kelamin, alamat, nik, no_hp FROM patients WHERE id = %s"
    cur.execute(query_bio, (patient_id,))
    patient_data = cur.fetchone()
    
    biodata = {
        'nama': patient_data[0], 
        'umur': patient_data[1], 
        'jenis_kelamin': patient_data[2],
        'alamat': patient_data[3], 
        'nik': patient_data[4], 
        'no_hp': patient_data[5]
    } if patient_data else {}

    # ==========================================
    # 2. DATA UNTUK GRAFIK (Chart)
    # ==========================================
    # Mengambil data: Tanggal, Kolesterol, Asam Urat, Gula
    # Urutan: ASC (Lama ke Baru)
    # Catatan: Pastikan nama kolom tanggal di DB Anda 'measurement_date' atau 'measured_at' (sesuaikan)
    query_chart = """
        SELECT measured_at, cholesterol_value, uric_acid_value, blood_sugar_value
        FROM measurements
        WHERE patient_id = %s
    """
    params = [patient_id]

    if start_date and end_date:
        query_chart += " AND measured_at >= %s AND measured_at <= %s"
        params.extend([start_date, end_date])
    
    query_chart += " ORDER BY measured_at ASC"

    cur.execute(query_chart, tuple(params))
    measurements_asc = cur.fetchall()

    chart_data = {
        'labels': [],
        'cholesterol': [],
        'uric_acid': [],
        'blood_sugar': [],
    }

    for m in measurements_asc:
        # m[0] = tanggal, m[1] = kol, m[2] = au, m[3] = gula
        tgl_str = m[0].strftime('%d-%m %H:%M') if m[0] else '-'
        chart_data['labels'].append(tgl_str)
        chart_data['cholesterol'].append(m[1])
        chart_data['uric_acid'].append(m[2])
        chart_data['blood_sugar'].append(m[3])

    # ==========================================
    # 3. DATA UNTUK TABEL RIWAYAT (History)
    # ==========================================
    # Mengambil SEMUA data termasuk Tensi, Tinggi, Berat
    # Urutan: DESC (Baru ke Lama) agar tabel menampilkan data terbaru di atas
    query_history = """
        SELECT 
            measured_at, 
            cholesterol_value, 
            uric_acid_value, 
            blood_sugar_value,
            blood_pressure_sys, 
            blood_pressure_dia, 
            height, 
            weight
        FROM measurements
        WHERE patient_id = %s
    """
    # Gunakan params yang sama (tapi kita buat list baru agar aman)
    params_hist = [patient_id]
    if start_date and end_date:
        query_history += " AND measured_at >= %s AND measured_at <= %s"
        params_hist.extend([start_date, end_date])

    query_history += " ORDER BY measured_at DESC"

    cur.execute(query_history, tuple(params_hist))
    measurements_desc = cur.fetchall()

    history_list = []
    for row in measurements_desc:
        # Kita map manual tuple ke dictionary agar JavaScript bisa membacanya
        # row[0]=Date, [1]=Kol, [2]=AU, [3]=Gula, [4]=Sys, [5]=Dia, [6]=Height, [7]=Weight
        history_list.append({
            'measured_at': row[0], # Objek date asli
            'formatted_date': row[0].strftime('%d-%m-%Y %H:%M') if row[0] else '-',
            'cholesterol_value': row[1],
            'uric_acid_value': row[2],
            'blood_sugar_value': row[3],
            'blood_pressure_sys': row[4],
            'blood_pressure_dia': row[5],
            'height': row[6],
            'weight': row[7]
        })

    cur.close()
    conn.close()

    return jsonify({
        'biodata': biodata, 
        'chart_data': chart_data,
        'history': history_list  # <--- Data ini yang akan masuk ke tabel
    })


@app.route('/upload_patient_data/<int:patient_id>', methods=['POST'])
def upload_patient_data(patient_id):
    """Mengupload data pasien spesifik (bisa difilter tanggal)."""
    if g.user is None: return jsonify({'status': 'error', 'message': 'Akses ditolak'}), 401
    
    # Ambil filter tanggal dari JSON body
    data = request.json
    start_date = data.get('start_date')
    end_date = data.get('end_date')

    conn = get_db_connection()
    cur = conn.cursor()
    
    query = """
        SELECT p.nama_lengkap, p.nik, p.umur, p.jenis_kelamin,
               m.measured_at, m.cholesterol_value, m.uric_acid_value, m.blood_sugar_value, 
               m.blood_pressure_sys, m.blood_pressure_dia, m.height, m.weight
        FROM measurements m
        JOIN patients p ON m.patient_id = p.id
        WHERE p.id = %s
    """
    params = [patient_id]

    if start_date and end_date:
        query += " AND m.measured_at >= %s AND m.measured_at <= %s"
        params.extend([start_date, end_date])
    
    query += " ORDER BY m.measured_at ASC"

    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        return jsonify({'status': 'warning', 'message': 'Tidak ada data pada rentang waktu ini.'})

    # Format ke JSON
    payload = []
    for row in rows:
        payload.append({
            "nama_pasien": row[0], "nik": row[1], "umur": row[2], "jenis_kelamin": row[3],
            "tanggal_pengukuran": row[4].isoformat(),
            "kolesterol": row[5], "asam_urat": row[6], "gula_darah": row[7],
            "tensi_sys": row[8], "tensi_dia": row[9],
            "tinggi_badan": row[10], "berat_badan": row[11]
        })

    # Kirim ke API Eksternal
    external_api_url = os.getenv('EXTERNAL_API_URL')
    if not external_api_url:
        return jsonify({'status': 'error', 'message': 'URL API eksternal belum disetting di .env'}), 500

    try:
        # response = requests.post(external_api_url, json=payload, timeout=30)
        # response.raise_for_status()
        # Simulasi sukses jika API belum ada:
        print(f"Mengupload {len(payload)} data ke {external_api_url}")
        return jsonify({'status': 'success', 'message': f'Berhasil mengunggah {len(payload)} data pasien ini!'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Gagal upload: {str(e)}'}), 500

@app.route('/api/patient/<int:patient_id>')
def get_patient_detail(patient_id):
    """API untuk mengambil data detail satu pasien."""
    if g.user is None:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, nama_lengkap, jenis_kelamin, alamat, umur, nik, no_hp FROM patients WHERE id = %s", (patient_id,))
    patient_data = cur.fetchone()
    cur.close()
    conn.close()

    if patient_data is None:
        return jsonify({'error': 'Patient not found'}), 404

    patient_dict = {
        'id': patient_data[0],
        'nama_lengkap': patient_data[1],
        'jenis_kelamin': patient_data[2],
        'alamat': patient_data[3],
        'umur': patient_data[4],
        'nik': patient_data[5],
        'no_hp': patient_data[6]
    }
    return jsonify(patient_dict)

@app.route('/patient/edit/<int:patient_id>', methods=['POST'])
def edit_patient(patient_id):
    """Menerima data dari form edit dan mengupdate database."""
    if g.user is None:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.form
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE patients
            SET nama_lengkap = %s, jenis_kelamin = %s, alamat = %s, umur = %s, nik = %s, no_hp = %s
            WHERE id = %s
            """,
            (data['nama_lengkap'], data['jenis_kelamin'], data['alamat'], data['umur'], data['nik'], data['no_hp'], patient_id)
        )
        conn.commit()
        return jsonify({'status': 'success', 'message': 'Data pasien berhasil diperbarui!'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': f'Gagal memperbarui data: {e}'}), 500
    finally:
        cur.close()
        conn.close()
        
@app.route('/patient/delete/<int:patient_id>', methods=['POST'])
def delete_patient(patient_id):
    """Menghapus data pasien dan semua data pengukurannya."""
    if g.user is None:
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Karena kita sudah mengatur ON DELETE CASCADE di database,
        # menghapus pasien akan otomatis menghapus semua data pengukurannya.
        cur.execute("DELETE FROM patients WHERE id = %s", (patient_id,))
        conn.commit()
        return jsonify({'status': 'success', 'message': 'Data pasien berhasil dihapus!'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': f'Gagal menghapus data: {e}'}), 500
    finally:
        cur.close()
        conn.close()
        
@app.route('/export/all')
def export_all():
    """Membuat file CSV dari semua data pengukuran dan mengirimkannya sebagai unduhan."""
    if g.user is None:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    # Query untuk mengambil semua data yang relevan dengan menggabungkan tabel
    cur.execute("""
        SELECT
            p.nama_lengkap,
            p.nik,
            p.umur,
            p.jenis_kelamin,
            m.measured_at,
            m.cholesterol_value,
            m.uric_acid_value,
            m.blood_sugar_value,
            m.blood_pressure_sys,
            m.blood_pressure_dia,
            m.height,
            m.weight
        FROM measurements m
        JOIN patients p ON m.patient_id = p.id
        ORDER BY p.nama_lengkap, m.measured_at;
    """)
    all_data = cur.fetchall()
    cur.close()
    conn.close()

    # Proses pembuatan file CSV di memori
    output = io.StringIO()
    writer = csv.writer(output)

    # Tulis baris header
    writer.writerow(['Nama Pasien', 'NIK', 'Umur', 'Jenis Kelamin', 'Tanggal Pengukuran', 'Kolesterol (mg/dL)', 'Asam Urat (mg/dL)', 'Gula Darah (mg/dL)', 'Tensi Sys (mmHg)', 'Tensi Dia (mmHg)', 'Tinggi Badan (cm)', 'Berat Badan (kg)'])

    # Tulis semua baris data
    for row in all_data:
        writer.writerow(row)

    output.seek(0) # Kembali ke awal file 'virtual'

    # Kirim file ke browser sebagai unduhan
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=semua_data_pengukuran.csv"}
    )
    
@app.route('/export/selected')
def export_selected():
    """Membuat file CSV dari riwayat pengukuran pasien yang dipilih."""
    if g.user is None:
        return redirect(url_for('login'))

    # Ambil daftar ID dari parameter URL, contoh: /export/selected?ids=1,2,5
    patient_ids = request.args.get('ids')
    if not patient_ids:
        flash('Tidak ada pasien yang dipilih untuk diekspor.', 'warning')
        return redirect(url_for('data_pengukuran'))

    # Ubah string "1,2,5" menjadi tuple integer (1, 2, 5) untuk query SQL
    ids_tuple = tuple(int(pid) for pid in patient_ids.split(','))

    conn = get_db_connection()
    cur = conn.cursor()
    
    # Query sama seperti export_all, tapi dengan klausa WHERE IN (...)
    cur.execute(f"""
        SELECT
            p.nama_lengkap, p.nik, p.umur, p.jenis_kelamin,
            m.measured_at, m.cholesterol_value, m.uric_acid_value, m.blood_sugar_value, 
            m.blood_pressure_sys, m.blood_pressure_dia, m.height, m.weight
        FROM measurements m
        JOIN patients p ON m.patient_id = p.id
        WHERE p.id IN %s
        ORDER BY p.nama_lengkap, m.measured_at;
    """, (ids_tuple,)) # Masukkan tuple ke dalam query
    
    selected_data = cur.fetchall()
    cur.close()
    conn.close()

    if not selected_data:
        flash('Tidak ada data pengukuran untuk pasien yang dipilih.', 'warning')
        return redirect(url_for('data_pengukuran'))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Nama Pasien', 'NIK', 'Umur', 'Jenis Kelamin', 'Tanggal Pengukuran', 'Kolesterol (mg/dL)', 'Asam Urat (mg/dL)', 'Gula Darah (mg/dL)', 'Tensi Sys (mmHg)', 'Tensi Dia (mmHg)', 'Tinggi Badan (cm)', 'Berat Badan (kg)'])
    writer.writerows(selected_data)
    
    output.seek(0)
    
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=data_pengukuran_terpilih.csv"}
    )
    
@app.route('/export/patient/<int:patient_id>')
def export_patient(patient_id):
    """Membuat file CSV dari riwayat pengukuran satu pasien."""
    if g.user is None:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    
    # Query untuk mengambil semua riwayat pengukuran dari SATU pasien
    cur.execute("""
        SELECT
            p.nama_lengkap, p.nik, p.umur, p.jenis_kelamin,
            m.measured_at, m.cholesterol_value, m.uric_acid_value, m.blood_sugar_value, 
            m.blood_pressure_sys, m.blood_pressure_dia, m.height, m.weight
        FROM measurements m
        JOIN patients p ON m.patient_id = p.id
        WHERE p.id = %s
        ORDER BY m.measured_at;
    """, (patient_id,))
    patient_data = cur.fetchall()
    cur.close()
    conn.close()

    if not patient_data:
        flash(f'Tidak ada data pengukuran untuk pasien dengan ID {patient_id}.', 'warning')
        return redirect(url_for('data_pengukuran'))

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(['Nama Pasien', 'NIK', 'Umur', 'Jenis Kelamin', 'Tanggal Pengukuran', 'Kolesterol (mg/dL)', 'Asam Urat (mg/dL)', 'Gula Darah (mg/dL)', 'Tensi Sys (mmHg)', 'Tensi Dia (mmHg)', 'Tinggi Badan (cm)', 'Berat Badan (kg)'])
    writer.writerows(patient_data)
    
    output.seek(0)
    
    # Membuat nama file dinamis berdasarkan nama pasien
    patient_name = patient_data[0][0].replace(' ', '_').lower()
    filename = f"data_pengukuran_{patient_name}.csv"

    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

if __name__ == '__main__':
    # Pastikan database berjalan
    try:
        get_db_connection().close()
        # create_default_admin() 
    except psycopg2.OperationalError as e:
        print(f"Koneksi ke database gagal: {e}")

    # Jalankan server web Flask-SocketIO
    print("Menjalankan server web Flask...")
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)