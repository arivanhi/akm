# Langkah 1: Gunakan base image Python
FROM python:3.10-slim

# Langkah 2: Tentukan folder kerja
WORKDIR /app

# Langkah 3: Install dependencies sistem
# Kita menggabungkan libusb (lama) dan BLUEZ (baru untuk bluetooth)
RUN apt-get update && apt-get install -y \
    libusb-1.0-0 \
    libusb-1.0-0-dev \
    bluez \
    libglib2.0-dev \
    && rm -rf /var/lib/apt/lists/*

# Langkah 4: Install Python dependencies
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Langkah 5: Salin semua kode (termasuk app.py, ble_scale_service.py, start.sh)
COPY . .

# Langkah 6: Berikan izin eksekusi ke script start.sh
# (Pastikan Anda sudah membuat file start.sh di folder project Anda)
RUN chmod +x start.sh

# Langkah 7: Expose port
EXPOSE 5000

# Langkah 8: Jalankan Script Manager (start.sh)
# Script ini yang akan menjalankan ble_scale_service.py DAN flask secara bersamaan
CMD ["./start.sh"]