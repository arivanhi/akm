import os
import io
import csv
import psycopg2
import bcrypt
import asyncio
import json
from flask import Flask, render_template, request, redirect, url_for, flash, session, g, jsonify, Response
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
import requests
import tensorflow as tf
import xgboost as xgb
import numpy as np
from sklearn.preprocessing import LabelEncoder
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import confusion_matrix, accuracy_score



# Muat environment variables dari file .env
load_dotenv()

MQTT_BROKER_HOST = os.getenv('MQTT_BROKER_HOST', 'localhost')
MQTT_DATA_TOPIC = "akm/data"
MQTT_COMMAND_TOPIC = "akm/command"
MQTT_PREDICTION_TOPIC = "akm/prediction_data"
MQTT_RESULT_TOPIC = "akm/prediction_result"
MQTT_PROGRESS_TOPIC = "akm/progress" 

load_modelxg_as_path = 'model/xgboost_as2_model.json'
load_modelknn_as_path = 'model/knn_as2_predictions.npy'

load_modelxg_kol_path = 'model/xgboost_kolesterol2_model.json'
load_modelknn_kol_path = 'model/knn_kolesterol2_predictions.npy'

load_modelxg_glu_path = 'model/xgboost_model.json'
load_modelknn_glu_path = 'model/knn_predictions.npy'

label_encoder = LabelEncoder()
print("Loading model xboost and predictions from saved files...")
try:
    xgb_model_as = xgb.XGBClassifier()
    xgb_model_as.load_model(load_modelxg_as_path)
    knn_predictions_as = np.load(load_modelknn_as_path)
    print("Model Asam Urat loaded successfully.")
    xgb_model_kol = xgb.XGBClassifier()
    xgb_model_kol.load_model(load_modelxg_kol_path)
    knn_predictions_kol = np.load(load_modelknn_kol_path)
    print("Model Kolesterol loaded successfully.")
    xgb_model_glu = xgb.XGBClassifier()
    xgb_model_glu.load_model(load_modelxg_glu_path)
    knn_predictions_glu = np.load(load_modelknn_glu_path)
    print("Model Gula Darah loaded successfully.")
except Exception as e:
    print(f"Error loading models: {e}")
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

# load model

# --- Fungsi-fungsi Bantuan & Middleware (Tidak Berubah) ---
# --- Logika MQTT Client ---
def on_connect(client, userdata, flags, rc):
    print(f"Terhubung ke MQTT Broker dengan hasil: {rc}")
    client.subscribe(MQTT_DATA_TOPIC)
    client.subscribe(MQTT_PREDICTION_TOPIC)
    client.subscribe(MQTT_RESULT_TOPIC)
    client.subscribe(MQTT_PROGRESS_TOPIC)
    print(f"Subscribe ke topik: {MQTT_DATA_TOPIC}, {MQTT_RESULT_TOPIC}, {MQTT_PROGRESS_TOPIC} dan {MQTT_PREDICTION_TOPIC}")

# def on_message(client, userdata, msg):
#     """Menerima data dari MQTT dan meneruskannya apa adanya ke browser."""
#     payload = msg.payload.decode('utf-8')
#     print(f"Data diterima dari MQTT topik '{msg.topic}': {payload}")
    
#     parts = payload.split(':')
#     if len(parts) == 2:
#         tipe, nilai_str = parts[0].strip(), parts[1].strip()
#         try:
#             nilai = float(nilai_str)
#         except ValueError:
#             nilai = nilai_str # Ini akan menjadi "STOP"
#         socketio.emit('measurement_update', {'type': tipe, 'value': nilai})

def on_message(client, userdata, msg):
    """Menerima data dari MQTT, lakukan prediksi, dan kirim hasil ke browser."""
    payload = msg.payload.decode('utf-8')
    
    if msg.topic == MQTT_PREDICTION_TOPIC:
        print(f"Data diterima dari MQTT topik '{msg.topic}': {payload}")
        print("Menerima data prediksi...")
        try:
            sensor_package = json.loads(payload)
            data_type = sensor_package.get('type')
            sensor_data = sensor_package.get('data')
            
            if not sensor_data or not data_type:
                raise ValueError("Data atau tipe tidak lengkap.")
            data_np = np.array([sensor_data])
            hasil_akhir = 0.0
            numeric_value = round(sum(sensor_data) / len(sensor_data), 2)
            
            if data_type == 'asam_urat' and xgb_model_as:
                xgb_pred = xgb_model_as.predict(data_np)
                # xgb_pred_encode = label_encoder.inverse_transform(xgb_pred)
                knn_pred = knn_predictions_as
                hasil_akhir = (xgb_pred[0] + knn_pred[0]) / 2
                print(f"Prediksi Asam Urat: {hasil_akhir}")
            
            elif data_type == 'cholesterol' and xgb_model_kol:
                xgb_pred = xgb_model_kol.predict(data_np)
                # xgb_pred_encode = label_encoder.inverse_transform(xgb_pred)
                knn_pred = knn_predictions_kol
                hasil_akhir = (xgb_pred[0] + knn_pred[0]) / 2
                print(f"Prediksi Kolesterol: {hasil_akhir}")
            
            elif data_type == 'gula_darah' and xgb_model_glu:
                xgb_pred = xgb_model_glu.predict(data_np)
                # xgb_pred_encode = label_encoder.inverse_transform(xgb_pred)
                knn_pred = knn_predictions_glu
                hasil_akhir = (xgb_pred[0] + knn_pred[0]) / 2
                print(f"Prediksi Gula Darah: {hasil_akhir}")
                
            result_payload = {
                'type': data_type,
                'value': float(hasil_akhir),
                # 'numeric_value': numeric_value
            }
            client.publish(MQTT_RESULT_TOPIC, json.dumps(result_payload))
        except Exception as e:
            print(f"Gagal memproses data prediksi: {e}")
    elif msg.topic == MQTT_RESULT_TOPIC:
        print(f"Data hasil prediksi diterima dari MQTT topik '{msg.topic}': {payload}")
        try:
            result_data = json.loads(payload)
            socketio.emit('prediction_result', result_data)
        except Exception as e:
            print(f"Gagal memproses data hasil prediksi: {e}")
    elif msg.topic == MQTT_PROGRESS_TOPIC:
        try:
            progress_data = json.loads(payload)
            # Langsung teruskan info progres ke browser
            socketio.emit('measurement_progress', progress_data)
        except Exception as e:
            print(f"Gagal mem-parsing progres: {e}")
        
    if msg.topic == MQTT_DATA_TOPIC:
        parts = payload.split(':')
        if len(parts) == 2:
            tipe, nilai_str = parts[0].strip(), parts[1].strip()
            try:
                nilai = float(nilai_str)
            except ValueError:
                nilai = nilai_str # Ini akan menjadi "STOP"
            socketio.emit('measurement_update', {'type': tipe, 'value': nilai})

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
    flag = data.get('flag')
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

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO measurements (patient_id, user_id, cholesterol_value, uric_acid_value, blood_sugar_value)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (patient_id, user_id, cholesterol, uric_acid, blood_sugar)
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

@app.route('/api/patient_measurements/<int:patient_id>')
def get_patient_measurements(patient_id):
    if g.user is None:
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db_connection()
    cur = conn.cursor()

    # Query 1: Ambil data biodata pasien
    cur.execute(
        "SELECT nama_lengkap, umur, jenis_kelamin, alamat, nik, no_hp FROM patients WHERE id = %s",
        (patient_id,)
    )
    patient_data = cur.fetchone()
    biodata = {
        'nama': patient_data[0],
        'umur': patient_data[1],
        'jenis_kelamin': patient_data[2],
        'alamat': patient_data[3],
        'nik': patient_data[4],
        'no_hp': patient_data[5]
    } if patient_data else {}

    # Query 2: Ambil semua riwayat pengukuran untuk chart
    cur.execute(
        """
        SELECT measured_at, cholesterol_value, uric_acid_value, blood_sugar_value
        FROM measurements
        WHERE patient_id = %s
        ORDER BY measured_at ASC;
        """, 
        (patient_id,)
    )
    measurements = cur.fetchall()
    cur.close()
    conn.close()

    chart_data = {
        'labels': [m[0].strftime('%d %b %Y %H:%M') for m in measurements],
        'cholesterol': [m[1] for m in measurements],
        'uric_acid': [m[2] for m in measurements],
        'blood_sugar': [m[3] for m in measurements],
    }

    # Gabungkan kedua data dalam satu response JSON
    return jsonify({'biodata': biodata, 'chart_data': chart_data})

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
            m.blood_sugar_value
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
    writer.writerow(['Nama Pasien', 'NIK', 'Umur', 'Jenis Kelamin', 'Tanggal Pengukuran', 'Kolesterol (mg/dL)', 'Asam Urat (mg/dL)', 'Gula Darah (mg/dL)'])

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
            m.measured_at, m.cholesterol_value, m.uric_acid_value, m.blood_sugar_value
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
    writer.writerow(['Nama Pasien', 'NIK', 'Umur', 'Jenis Kelamin', 'Tanggal Pengukuran', 'Kolesterol (mg/dL)', 'Asam Urat (mg/dL)', 'Gula Darah (mg/dL)'])
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
            m.measured_at, m.cholesterol_value, m.uric_acid_value, m.blood_sugar_value
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

    writer.writerow(['Nama Pasien', 'NIK', 'Umur', 'Jenis Kelamin', 'Tanggal Pengukuran', 'Kolesterol (mg/dL)', 'Asam Urat (mg/dL)', 'Gula Darah (mg/dL)'])
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