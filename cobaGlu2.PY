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

# Buat y_train berdasarkan hasil yang dijelaskan
#y_train = np.zeros((300, df.shape[1]))  # Inisialisasi array kosong untuk y_train

# Proses untuk mengisi y_train sesuai deskripsi
#for i in range(df.shape[1]):
#    y_train[:, i] = hasil[i]

# Cetak X_train dan y_train untuk memeriksa
print("Data X_train (sample data):")
print(X_train)

print("\nData y_train (hasil):")
print(Y_train)

# Langkah 6: Menggunakan KNN
k = 1  # Atur jumlah tetangga sesuai kebutuhan Anda
mdl = KNeighborsClassifier(n_neighbors=k)
mdl.fit(X_train, Y_train)

# Langkah 7: Evaluasi Model
Y_pred = mdl.predict(X_train)  # Anda dapat mengganti X_train dengan X_test jika sudah membagi data

# Melakukan evaluasi performa model
# Misalnya, menampilkan confusion matrix
confusionMat = confusion_matrix(Y_train, Y_pred)
print('Confusion Matrix:')
print(confusionMat)

# Menghitung akurasi
accuracy = accuracy_score(Y_train, Y_pred)
print('Akurasi:', accuracy)

# Menampilkan Y_train dan Y_pred dalam matriks A
A = np.vstack((Y_train, Y_pred)).T
print('Matriks A (Y_train dan Y_pred):')
print(A)
