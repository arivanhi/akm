import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.neighbors import KNeighborsRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
import joblib
import os

# --- KONFIGURASI ---
FILE_PATH = 'data ADC Glukosa.xlsx' # Pastikan nama file benar
SHEET_NAME = 'Sheet1'
TARGET_MODEL_XGB = 'model/xgboost_glukosa_regressor.json'
TARGET_MODEL_KNN = 'model/knn_glukosa_regressor.pkl'

# Pastikan folder model ada
if not os.path.exists('model'):
    os.makedirs('model')

print(f"Memuat data dari {FILE_PATH}...")

# 1. LOAD DATA
# Load Fitur (X) - Baris 2 s/d 251 (250 fitur)
df_X = pd.read_excel(FILE_PATH, sheet_name=SHEET_NAME, header=None, skiprows=1, nrows=250, usecols='A:PD')

# Load Label (y) - Baris 1 (Target nilai glukosa)
df_y = pd.read_excel(FILE_PATH, sheet_name=SHEET_NAME, header=None, nrows=1, usecols='A:PD')

# 2. TRANSPOSE & FORMATTING
print("Melakukan transpose dan formatting...")
X = df_X.to_numpy().T # Transpose: (250, 420) -> (420, 250)
y = df_y.to_numpy().flatten() # (1, 420) -> (420,)

print(f"Dimensi Awal -> X: {X.shape}, y: {y.shape}")

# 3. PEMBERSIHAN DATA (Hapus NaN)
# Kita gabungkan dulu X dan y ke dalam DataFrame sementara untuk mempermudah penghapusan baris NaN
df_combined = pd.DataFrame(X)
df_combined['target'] = y

print(f"Jumlah sampel sebelum pembersihan: {len(df_combined)}")
df_combined = df_combined.dropna()
print(f"Jumlah sampel setelah dihapus NaN: {len(df_combined)}")

# Pisahkan kembali
X = df_combined.drop(columns=['target']).to_numpy()
y = df_combined['target'].to_numpy()

# 4. PREPROCESSING
# Bulatkan dan ubah ke integer (sesuai standar Anda)
X = np.round(X).astype(int)
# y = np.round(y).astype(int) # Target boleh float atau int

# 5. SPLIT DATA
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# --- 6. TRAINING KNN REGRESSOR ---
print("\n--- Training KNN Regressor ---")
knn = KNeighborsRegressor(n_neighbors=3)
knn.fit(X_train, y_train)

# Evaluasi
knn_pred = knn.predict(X_test)
print(f"KNN Mean Absolute Error: {mean_absolute_error(y_test, knn_pred):.4f}")

# Simpan KNN
joblib.dump(knn, TARGET_MODEL_KNN)
print(f"Model KNN disimpan ke: {TARGET_MODEL_KNN}")

# --- 7. TRAINING XGBOOST REGRESSOR ---
print("\n--- Training XGBoost Regressor ---")
xgb_model = xgb.XGBRegressor(objective='reg:squarederror', n_estimators=100)
xgb_model.fit(X_train, y_train)

# Evaluasi
xgb_pred = xgb_model.predict(X_test)
print(f"XGBoost Mean Absolute Error: {mean_absolute_error(y_test, xgb_pred):.4f}")

# Simpan XGBoost
xgb_model.save_model(TARGET_MODEL_XGB)
print(f"Model XGBoost disimpan ke: {TARGET_MODEL_XGB}")

print("\nSelesai! Siap digunakan di app.py.")