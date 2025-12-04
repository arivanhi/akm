import numpy as np
import xgboost as xgb
import joblib
import os

# --- 1. DATA SENSOR (120 Fitur Asam Urat) ---
sensor_data = [
    33.16,24.04,25.58,59.78,942.39,1802.86,39.8,28.04,34.11,80.99,
    1292.86,1945.1,42.01,29.38,35.17,81.96,1308.14,2006.7,42.01,29.38,
    35.17,82.92,1310.18,2035.69,42.01,29.38,35.17,81.96,1298.97,2043.85,
    42.01,29.38,35.17,81.96,1298.97,2065.59,43.11,30.72,36.24,83.89,
    1316.29,2107.26,43.11,30.72,35.17,82.92,1313.23,2107.26,42.01,29.38,
    35.17,81.96,1290.82,2088.24,40.9,29.38,34.11,80.03,1257.2,2060.15,
    40.9,29.38,34.11,79.06,1248.03,2063.78,40.9,28.04,34.11,77.14,
    1222.56,2035.69,39.8,28.04,33.04,75.21,1192,2001.27,38.69,28.04,
    31.97,74.24,1174.68,1987.68,38.69,28.04,31.97,74.24,1165.51,1982.24,
    38.69,28.04,31.97,72.31,1149.21,1966.84,38.69,26.71,31.97,72.31,
    1142.07,1964.12,38.69,26.71,31.97,72.31,1140.04,1970.46,37.59,26.71,
    31.97,71.35,1133.92,1965.93,37.59,26.71,30.91,71.35,1128.83,1965.03
]

# --- KONFIGURASI PATH MODEL ---
# Pastikan nama file ini sesuai dengan output dari train_regression.py
XGB_MODEL_PATH = 'model/xgboost_asam_urat_regressor.json'
KNN_MODEL_PATH = 'model/knn_asam_urat_regressor.pkl'

def run_test():
    print("=" * 50)
    print("TESTING MODEL ASAM URAT (REGRESI)")
    print("=" * 50)

    # 1. Cek File Model
    if not os.path.exists(XGB_MODEL_PATH) or not os.path.exists(KNN_MODEL_PATH):
        print(f"ERROR: File model tidak ditemukan.")
        print(f"Cek: {XGB_MODEL_PATH} dan {KNN_MODEL_PATH}")
        print("Pastikan Anda sudah menjalankan script 'train_regression.py'!")
        return

    try:
        # 2. Preprocessing Data
        print("\n[1] Preprocessing Data Sensor...")
        data_np = np.array(sensor_data)
        
        # Bulatkan dan ubah ke integer (Sesuai data training Anda)
        data_np = np.round(data_np).astype(int)
        
        # Reshape ke (1, 120)
        data_input = data_np.reshape(1, -1)
        print(f"    Shape input: {data_input.shape}")

        # 3. Load Models
        print("\n[2] Memuat Model Regressor...")
        
        # Load XGBoost Regressor
        xgb_model = xgb.XGBRegressor()
        xgb_model.load_model(XGB_MODEL_PATH)
        print("    XGBoost Regressor loaded.")

        # Load KNN Regressor (dari file .pkl)
        knn_model = joblib.load(KNN_MODEL_PATH)
        print("    KNN Regressor loaded.")

        # 4. Prediksi
        print("\n[3] Menjalankan Prediksi...")

        # Prediksi XGBoost (Langsung keluar angka)
        pred_xgb = xgb_model.predict(data_input)[0]
        print(f"    XGBoost Prediksi: {pred_xgb:.2f}")

        # Prediksi KNN (Langsung keluar angka)
        pred_knn = knn_model.predict(data_input)[0]
        print(f"    KNN Prediksi    : {pred_knn:.2f}")

        # Ensemble (Rata-rata)
        final_result = (pred_xgb + pred_knn) / 2
        
        # --- KOREKSI SKALA (Opsional) ---
        # Jika data training Anda dikali 10 (misal: 54 artinya 5.4), 
        # aktifkan baris di bawah ini:
        # final_result = final_result / 10
        
        print("\n" + "=" * 50)
        print(f"HASIL AKHIR ASAM URAT: {final_result:.2f} mg/dL")
        print("=" * 50)

    except Exception as e:
        print(f"\n!!! TERJADI ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()