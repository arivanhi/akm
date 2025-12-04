import numpy as np
import xgboost as xgb
import joblib
import os

# --- 1. DATA SENSOR MENTAH (12-BIT) ---
# Data yang Anda berikan (panjang 130)
sensor_data_raw = [0,0,1844,3047,1904,2139,1207,1691,1666,1662,2018,1213,1153,1344,1232,1451,1078,1245,1206,1396,1409,1419,1615,1639,1681,1699,1991,1713,1719,1582,1691,1671,1789,1697,1600,1709,1807,1900,1969,1823,1865,1988,1969,2033,2191,2163,1843,1860,2259,2041,2046,2175,2269,2809,2559,2406,2368,1989,2145,1872,1983,1918,1907,2007,1955,1769,1808,1793,1837,1809,2062,1883,1633,1602,1724,1696,1810,1819,1789,1890,1840,1825,1826,1883,1831,1815,1705,1463,1470,2081,1962,2068,2256,1443,2225,1775,2215,2400,2144,2353,2607,2623,2622,2604,2626,2704,2799,2927,2912,2871,2869,2874,2838,2794,2775,2736,2751,2637,2661,2833,2779,2790,2793,2896,2768,2698,2811,2826,2675,2730,2594,2582,2625,2638,2629,2655,2686,2688,2771,2766,2671,2688,2621,2605,2622,2637,2559,2559,2599,2657,2661,2683,2590,2467,2490,2461,2345,2309,2267,2160,2103,2014,1958,1939,1939,2021,2112,2099,1977,1904,1930,2067,2197,2129,2210,2224,2224,2272,2355,2453,2299,2439,2421,2234,2249,2253,2221,2405,2303,2220,2304,2279,2480,2483,2429,2559,2429,2507,2481,2381,2379,2390,2479,2350,2343,2413,2387,2399,2503,2520,2498,2426,2361,2368,2416,2437,2387,2275,1968,2079,2041,2172,2214,2201,2415,2367,2478,2506,2544,2517,2474,2459,2356,2471,2450,2443,2510,2551,2451,2399,2617,2597,2555,2608,2653,2559,2604,2544,2428,2559]
# --- KONFIGURASI MODEL ---
# Pastikan Anda sudah menjalankan train_glucose_regression.py sebelumnya
XGB_MODEL_PATH = 'model/xgboost_glukosa_regressor.json'
KNN_MODEL_PATH = 'model/knn_glukosa_regressor.pkl'

def run_test():
    print("=" * 50)
    print("TESTING MODEL GLUKOSA (REGRESI)")
    print("=" * 50)

    # 1. Cek File Model
    if not os.path.exists(XGB_MODEL_PATH) or not os.path.exists(KNN_MODEL_PATH):
        print(f"ERROR: File model tidak ditemukan.")
        print("Pastikan Anda sudah menjalankan script 'train_glucose_regression.py'!")
        return

    try:
        # 2. PREPROCESSING DATA
        print("\n[1] Preprocessing Data Sensor...")
        
        # Konversi List ke Numpy Array
        data_np = np.array(sensor_data_raw)
        print(f"    Panjang data awal (Raw): {len(data_np)}")

        # A. Konversi 12-bit (0-4095) ke 8-bit (0-255)
        # Rumus: (nilai / 4095) * 255
        data_8bit = (data_np / 4095.0) * 255.0
        data_8bit = np.round(data_8bit).astype(int)
        print(f"    Contoh data 8-bit: {data_8bit[:10]} ...")

        # B. Pengecekan Panjang Data (Wajib 250)
        target_length = 250
        current_length = len(data_8bit)
        
        if current_length < target_length:
            print(f"    ⚠️ PERINGATAN: Data kurang ({current_length}/{target_length}). Melakukan padding dengan 0.")
            # Tambahkan angka 0 di akhir array sampai panjangnya 250
            padding = np.zeros(target_length - current_length, dtype=int)
            data_8bit = np.concatenate((data_8bit, padding))
        elif current_length > target_length:
            print(f"    ⚠️ PERINGATAN: Data berlebih ({current_length}/{target_length}). Memotong data.")
            data_8bit = data_8bit[:target_length]
            
        print(f"    Panjang data final: {len(data_8bit)}")

        # C. Reshape ke (1, 250) untuk input model
        data_input = data_8bit.reshape(1, -1)
        print(f"    Shape input model: {data_input.shape}")

        # 3. LOAD MODELS
        print("\n[2] Memuat Model Regressor...")
        
        # Load XGBoost
        xgb_model = xgb.XGBRegressor()
        xgb_model.load_model(XGB_MODEL_PATH)
        print("    XGBoost Regressor loaded.")

        # Load KNN
        knn_model = joblib.load(KNN_MODEL_PATH)
        print("    KNN Regressor loaded.")

        # 4. PREDIKSI
        print("\n[3] Menjalankan Prediksi...")

        # Prediksi XGBoost
        pred_xgb = xgb_model.predict(data_input)[0]
        print(f"    XGBoost Prediksi: {pred_xgb:.2f}")

        # Prediksi KNN
        pred_knn = knn_model.predict(data_input)[0]
        print(f"    KNN Prediksi    : {pred_knn:.2f}")

        # Ensemble (Rata-rata)
        final_result = (pred_xgb + pred_knn) / 2
        
        print("\n" + "=" * 50)
        print(f"HASIL AKHIR GLUKOSA: {final_result:.2f} mg/dL")
        print("=" * 50)

    except Exception as e:
        print(f"\n!!! TERJADI ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()