# Langkah 1: Gunakan base image Python yang resmi dan ringan
FROM python:3.10-slim

# Langkah 2: Tentukan folder kerja di dalam container
WORKDIR /app

# Langkah 3: Salin file requirements dan install dependencies terlebih dahulu
# Ini memanfaatkan cache Docker agar tidak perlu install ulang setiap ada perubahan kode
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Langkah 4: Salin sisa kode aplikasi ke dalam container
COPY . .

# Langkah 5: Beri tahu Docker bahwa container akan listen di port 5000
EXPOSE 5000

# Langkah 6: Perintah untuk menjalankan aplikasi saat container启动
# Opsi --host=0.0.0.0 penting agar aplikasi bisa diakses dari luar container
CMD ["flask", "run", "--host=0.0.0.0"]