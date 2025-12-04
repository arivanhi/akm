import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.neighbors import KNeighborsRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
import joblib
import os

# --- KONFIGURASI ---
FILE_PATH = 'data/adc_kolesterol_v2.csv'  # Pastikan nama file CSV Anda benar
TARGET_MODEL_XGB = 'model/xgboost_kolesterol_regressor.json'
TARGET_MODEL_KNN = 'model/knn_kolesterol_regressor.pkl'

# Pastikan folder model ada
if not os.path.exists('model'):
    os.makedirs('model')

print(f"Memuat data dari {FILE_PATH}...")

# 1. LOAD DATA
# Asumsi file CSV memiliki header (red 1, red 2, ..., real)
df = pd.read_csv(FILE_PATH)


# --- PERBAIKAN: Hapus Baris yang Mengandung NaN ---
print(f"Jumlah data awal: {len(df)}")
if df.isnull().values.any():
    print("Ditemukan data kosong (NaN). Menghapus baris terkait...")
    df = df.dropna()
    print(f"Jumlah data setelah dibersihkan: {len(df)}")

# 2. MEMISAHKAN FITUR (X) DAN TARGET (y)
# Ambil 20 kolom pertama sebagai Fitur (red 1 - red 20)
X = df.iloc[:, 0:20].to_numpy()

# Ambil kolom ke-21 (terakhir) sebagai Target (real)
y = df.iloc[:, 20].to_numpy().ravel()

# 3. PREPROCESSING
# Sesuai standar Anda: Bulatkan dan ubah ke integer
print("Melakukan preprocessing data...")
X = np.round(X).astype(int)
# Target y tidak perlu dibulatkan jika ingin presisi, tapi jika data latihnya int, int saja tidak masalah.
# y = np.round(y).astype(int) 

print(f"Dimensi X: {X.shape} (Sampel x 20 Fitur)")
print(f"Dimensi y: {y.shape}")
print(f"Contoh X (baris pertama): {X[0]}")
print(f"Contoh y (baris pertama): {y[0]}")

# 4. SPLIT DATA
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# --- 5. TRAINING KNN REGRESSOR ---
print("\n--- Training KNN Regressor ---")
# n_neighbors bisa disesuaikan (misal 3, 5, 7). Default 5 biasanya oke.
knn = KNeighborsRegressor(n_neighbors=3) 
knn.fit(X_train, y_train)

# Evaluasi KNN
knn_pred = knn.predict(X_test)
mae_knn = mean_absolute_error(y_test, knn_pred)
print(f"KNN Mean Absolute Error: {mae_knn:.2f}")

# Simpan KNN
joblib.dump(knn, TARGET_MODEL_KNN)
print(f"Model KNN disimpan ke: {TARGET_MODEL_KNN}")

# --- 6. TRAINING XGBOOST REGRESSOR ---
print("\n--- Training XGBoost Regressor ---")
xgb_model = xgb.XGBRegressor(objective='reg:squarederror', n_estimators=100)
xgb_model.fit(X_train, y_train)

# Evaluasi XGBoost
xgb_pred = xgb_model.predict(X_test)
mae_xgb = mean_absolute_error(y_test, xgb_pred)
print(f"XGBoost Mean Absolute Error: {mae_xgb:.2f}")

# Simpan XGBoost
xgb_model.save_model(TARGET_MODEL_XGB)
print(f"Model XGBoost disimpan ke: {TARGET_MODEL_XGB}")

print("\nSelesai! Jangan lupa update app.py dan Node-RED.")