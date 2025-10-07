int currentMeasurementType = 0;  // 0 = Idle, 1 = Kolesterol, 2 = Asam Urat, 3 = Gula Darah

void setup() {
  // Mulai komunikasi serial dengan baud rate 9600, sesuaikan dengan di Python
  Serial.begin(9600);
  Serial.println("ESP32 siap. Menunggu perintah flag...");
  pinMode(13, INPUT_PULLUP);
}

void loop() {
  // 1. Cek apakah ada perintah masuk dari Raspberry Pi
  // Serial.println(digitalRead(13));
  if (Serial.available() > 0) {
    // Baca perintah yang masuk (diasumsikan dikirim dengan newline)
    String command = Serial.readStringUntil('\n');
    command.trim();  // Hapus spasi atau karakter tak terlihat

    int flag = command.toInt();

    // // Pastikan flag valid sebelum mengubah state
   
      currentMeasurementType = flag;
      // Serial.print(">>> Perintah diterima, memulai pengukuran untuk flag: ");
      // Serial.println(currentMeasurementType);
  
  }

  // 2. Kirim data hanya jika ada mode pengukuran yang aktif
  if (currentMeasurementType != 0) {
    String dataType;
    float randomValue;

    // Tentukan tipe data dan rentang angka random berdasarkan state
    switch (currentMeasurementType) {
      case 1:  // Kolesterol
        dataType = "cholesterol";
        randomValue = random(0, 301) / 10.0;  // Angka random 0.0 - 30.0
        break;
      case 2:  // Asam Urat
        dataType = "asam_urat";
        randomValue = random(310, 601) / 10.0;  // Angka random 31.0 - 60.0
        break;
      case 3:  // Gula Darah
        dataType = "gula_darah";
        randomValue = random(610, 1001) / 10.0;  // Angka random 61.0 - 100.0
        break;
      default:
        break;
    }

    // Format data menjadi string "tipe:nilai"
    String dataString = dataType + ":" + String(randomValue);

    // Kirim data kembali ke Raspberry Pi melalui serial
    
      Serial.println(dataString);
  }

  // Beri jeda 1 detik sebelum iterasi loop berikutnya
  delay(1000);
}