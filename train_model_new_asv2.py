import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.neighbors import KNeighborsRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
import joblib
import os

# Konfigurasi
FILE_PATH = 'data/adc_asam_urat_v3.csv' # Pastikan path file benar
TARGET_MODEL_XGB = 'model/xgboost_asam_urat_regressor.json'
TARGET_MODEL_KNN = 'model/knn_asam_urat_regressor.pkl'

if not os.path.exists('model'): os.makedirs('model')

print(f"Memuat data dari {FILE_PATH}...")
df = pd.read_csv(FILE_PATH)

# Ambil 120 Fitur (X)
X = df.iloc[:, 0:120].to_numpy()
X = np.round(X).astype(int)

# Ambil Label (y)
# PENTING: Pastikan nilai di kolom ini adalah angka mg/dL (misal 5.4, 6.2)
# Jika di CSV nilainya 54, 62 (dikalikan 10), nanti hasil prediksi juga harus dibagi 10
y = df.iloc[:, 120:].to_numpy().ravel() 

print(f"Contoh Label (y) 5 data pertama: {y[:5]}")

# Split Data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# --- 1. TRAINING KNN REGRESSOR ---
print("\nTraining KNN Regressor...")
# n_neighbors bisa disesuaikan, misal 3 atau 5
knn = KNeighborsRegressor(n_neighbors=3) 
knn.fit(X_train, y_train)

# Evaluasi
knn_pred = knn.predict(X_test)
print(f"KNN Mean Absolute Error: {mean_absolute_error(y_test, knn_pred):.4f}")

# Simpan
joblib.dump(knn, TARGET_MODEL_KNN)
print("Model KNN Regressor disimpan.")

# --- 2. TRAINING XGBOOST REGRESSOR ---
print("\nTraining XGBoost Regressor...")
# Menggunakan XGBRegressor untuk prediksi angka
xgb_model = xgb.XGBRegressor(objective='reg:squarederror', n_estimators=100)
xgb_model.fit(X_train, y_train)

# Evaluasi
xgb_pred = xgb_model.predict(X_test)
print(f"XGBoost Mean Absolute Error: {mean_absolute_error(y_test, xgb_pred):.4f}")

# Simpan
xgb_model.save_model(TARGET_MODEL_XGB)
print("Model XGBoost Regressor disimpan.")