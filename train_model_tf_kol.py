import pandas as pd
import numpy as np
import tensorflow as tf
import os
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


data = 'data/adc_kolesterol_v2.csv'

df = pd.read_csv(data,header=0)

print(f"Data asli: {len(df)} baris.")
print(f"Mengecek data yang hilang (NaN):\n{df.isnull().sum()}\n")

# Menghapus semua baris yang memiliki setidaknya satu nilai NaN
df = df.dropna()

print(f"Data setelah dibersihkan (dihapus NaN): {len(df)} baris.")
print(df.head())
X = df.iloc[:, 0:20].values
y = df.iloc[:, 20:].values
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
# --- 4. NORMALISASI DATA (LANGKAH PALING PENTING) ---
# Kita akan menormalisasi fitur (X) dan label (y)
x_scaler = StandardScaler()
y_scaler = StandardScaler()

# Latih (fit) scaler HANYA pada data training
X_train_scaled = x_scaler.fit_transform(X_train)
y_train_scaled = y_scaler.fit_transform(y_train)

# Terapkan (transform) scaler yang sama ke data test
X_test_scaled = x_scaler.transform(X_test)
y_test_scaled = y_scaler.transform(y_test)

print("Data X_train telah dinormalisasi.")
print(f"Data Y_train (skala asli, 5 baris pertama):\n{y_train[:5]}")
print(f"Data Y_train (skala baru, 5 baris pertama):\n{y_train_scaled[:5]}")

# --- 5. MEMBUAT MODEL ---
tf.random.set_seed(42)
model = tf.keras.Sequential([
    tf.keras.layers.InputLayer(input_shape=(20,)),
    tf.keras.layers.Dense(256, activation='relu'),
    tf.keras.layers.Dense(128, activation='relu'),
    tf.keras.layers.Dense(64, activation='relu'),
    tf.keras.layers.Dense(32, activation='relu'),
    tf.keras.layers.Dense(1, activation='linear') # Output linear untuk regresi
], name='kolesterol_model')

model.summary()

# --- 6. KOMPILASI MODEL ---
# Kita bisa gunakan learning rate default dari Adam dulu
model.compile(optimizer='adam', loss='mse', metrics=['mae'])
# (Jika masih NaN, coba kecilkan learning rate: 
#  optimizer=tf.keras.optimizers.Adam(learning_rate=0.0001))

# --- 7. TRAINING MODEL ---
print("\nMemulai training model...")
history = model.fit(
    X_train_scaled,         # Gunakan data X yang sudah dinormalisasi
    y_train_scaled,         # Gunakan data y yang sudah dinormalisasi
    epochs=100, 
    batch_size=8, 
    validation_data=(X_test_scaled, y_test_scaled) # Gunakan data test untuk validasi
)
print("Training selesai.")

# --- 8. MENYIMPAN MODEL DAN SCALER (PENTING) ---
save_path = os.path.join('model', 'model_kolesterol_VIS_2.h5')
model.save(save_path)
print(f"Model H5 disimpan di: {save_path}")