import pandas as pd
import numpy as np
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import confusion_matrix, accuracy_score

# Baca file Excel
file_path = 'data ADC Glukosa.xlsx'
sheet_name = 'Sheet1'
df = pd.read_excel(file_path, sheet_name=sheet_name)

# Membaca data dari sheet 1, mulai dari A2 ke EE300 untuk X
df_X = pd.read_excel(file_path, sheet_name='Sheet1', header=None, usecols="A:EE", skiprows=1, nrows=300)

# Mengambil nilai X dari DataFrame dan mengonversinya ke numpy array
X_train = df_X.to_numpy()
X_train = np.transpose(X_train)

# Membaca data dari sheet 1, mulai dari A1 ke EE1 untuk Y
df_Y = pd.read_excel(file_path, sheet_name='Sheet1', header=None, usecols="A:EE", nrows=1)

# Mengambil nilai Y dari DataFrame dan mengonversinya ke numpy array
Y_train = df_Y.to_numpy().flatten()

# Menampilkan dimensi X_train dan Y_train untuk memeriksa jumlah sampel
print("Dimensi X_train:", X_train.shape)
print("Dimensi Y_train:", Y_train.shape)

# Cetak X_train dan y_train untuk memeriksa
print("Data X_train (sample data):")
print(X_train)

print("\nData y_train (hasil):")
print(Y_train)

# Membuat model KNN
knn = KNeighborsClassifier(n_neighbors=2)  # Jumlah tetangga bisa disesuaikan

# Melatih model dengan data training
knn.fit(X_train, Y_train)

# Membuat data baru untuk diprediksi
# Data baru diambil secara random dari 2500 hingga 3500 sebanyak 300 array
X_new = np.random.randint(2500, 3500, (1, 300))

# Melakukan prediksi dengan model KNN
Y_pred = knn.predict(X_new)

# Menampilkan hasil prediksi
print("\nData baru (sample):")
print(X_new)

print("\nHasil prediksi:")
print(Y_pred)


