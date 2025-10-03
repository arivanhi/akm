-- Membuat tipe data ENUM untuk role agar lebih efisien dan aman
CREATE TYPE user_role AS ENUM ('admin', 'operator', 'pasien');

-- Membuat tabel untuk menyimpan data pengguna
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    nama VARCHAR(255) NOT NULL,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    no_hp VARCHAR(20) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role user_role NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- (Opsional) Memberi komentar pada kolom untuk kejelasan
COMMENT ON COLUMN users.password_hash IS 'Stores the hashed password, NOT the plain text password.';
COMMENT ON COLUMN users.is_active IS 'Becomes TRUE after user confirms their email.';

-- Membuat tabel untuk data pasien
CREATE TABLE patients (
    id SERIAL PRIMARY KEY,
    nama_lengkap VARCHAR(255) NOT NULL,
    jenis_kelamin VARCHAR(20),
    alamat TEXT,
    umur INT,
    nik VARCHAR(20) UNIQUE,
    no_hp VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Membuat index pada nama untuk pencarian lebih cepat
CREATE INDEX idx_patients_nama ON patients(nama_lengkap);

-- TAMBAHKAN KODE INI DI AKHIR FILE init.sql

-- Membuat tabel untuk menyimpan hasil pengukuran
CREATE TABLE measurements (
    id SERIAL PRIMARY KEY,
    patient_id INT NOT NULL,
    user_id INT NOT NULL,
    cholesterol_value FLOAT,
    uric_acid_value FLOAT,
    blood_sugar_value FLOAT,
    measured_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Menambahkan relasi ke tabel patients dan users
    CONSTRAINT fk_patient
        FOREIGN KEY(patient_id) 
        REFERENCES patients(id)
        ON DELETE CASCADE, -- Jika pasien dihapus, datanya juga terhapus

    CONSTRAINT fk_user
        FOREIGN KEY(user_id) 
        REFERENCES users(id)
);

COMMENT ON COLUMN measurements.user_id IS 'ID dari operator/user yang melakukan pengukuran.';