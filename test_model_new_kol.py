import numpy as np
import xgboost as xgb
import joblib
import os

# --- 1. DATA SENSOR (120 Fitur Asam Urat) ---
sensor_data = [49.4,50.55,50.55,50.55,50.55,50.55,50.55,50.55,49.4,49.4,49.4,49.4,49.4,49.4,49.4,49.4,49.4,49.4,49.4,49.4]

# --- KONFIGURASI PATH MODEL ---
# Pastikan nama file ini sesuai dengan output dari train_regression.py
XGB_MODEL_PATH = 'model/xgboost_kolesterol_regressor.json'
KNN_MODEL_PATH = 'model/knn_kolesterol_regressor.pkl'

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