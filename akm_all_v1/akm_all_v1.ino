#include "AS726X.h"
#define ledMerah 2
#define ledIr 17
#define ledGlu 16
#define photoDioda 4

AS726X sensor;

int currentMeasurementType = 0;  // 0 = Idle, 1 = Kolesterol, 2 = Asam Urat, 3 = Gula Darah

void TCA9548A(uint8_t bus) {
  Wire.beginTransmission(0x70);  // TCA9548A address is 0x70
  Wire.write(1 << bus);          // send byte to select bus
  Wire.endTransmission();
  // Serial.print(bus);
}

void setup() {
  Wire.begin();
  // Mulai komunikasi serial dengan baud rate 9600, sesuaikan dengan di Python
  Serial.begin(115200);
  // analogReadResolution(8);
  pinMode(ledMerah, OUTPUT);
  pinMode(ledIr, OUTPUT);
  pinMode(ledGlu, OUTPUT);

  TCA9548A(2);
  if (!sensor.begin()) {
    Serial.println("sensor failed to connect");
    for (;;)
      ;
  }
  TCA9548A(3);
  if (!sensor.begin()) {
    Serial.println("sensor failed to connect");
    for (;;)
      ;
  }
}

int glukosa() {
  int read;
  digitalWrite(ledGlu, HIGH);
  read = analogRead(photoDioda);
  // Serial.println(read);
  return read;
}

String asamUrat() {
  digitalWrite(ledMerah, HIGH);
  TCA9548A(2);
  float violet;
  float blue;
  float green;
  float yellow;
  float orange;
  float red;
  String data;

  sensor.takeMeasurements();
  violet = sensor.getCalibratedViolet();
  blue = sensor.getCalibratedBlue();
  green = sensor.getCalibratedGreen();
  yellow = sensor.getCalibratedYellow();
  orange = sensor.getCalibratedOrange();
  red = sensor.getCalibratedRed();

  data = String(violet);
  data += "," + String(blue);
  data += "," + String(green);
  data += "," + String(yellow);
  data += "," + String(orange);
  data += "," + String(red);

  return data;
}

String kolesterol() {
  digitalWrite(ledIr, HIGH);
  TCA9548A(3);
  float violet;
  float blue;
  float green;
  float yellow;
  float orange;
  float red;
  String data;

  sensor.takeMeasurements();
  violet = sensor.getCalibratedViolet();
  blue = sensor.getCalibratedBlue();
  green = sensor.getCalibratedGreen();
  yellow = sensor.getCalibratedYellow();
  orange = sensor.getCalibratedOrange();
  red = sensor.getCalibratedRed();

  data = String(violet);
  data += "," + String(blue);
  data += "," + String(green);
  data += "," + String(yellow);
  data += "," + String(orange);
  data += "," + String(red);

  return data;
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
    String value;

    // Tentukan tipe data dan rentang angka random berdasarkan state
    switch (currentMeasurementType) {
      case 1:  // Kolesterol
        dataType = "cholesterol";
        value = kolesterol();  // Angka random 0.0 - 30.0
        break;
      case 2:  // Asam Urat
        dataType = "asam_urat";
        value = asamUrat();  // Angka random 31.0 - 60.0
        break;
      case 3:  // Gula Darah
        dataType = "gula_darah";
        value = String(glukosa());  // Angka random 61.0 - 100.0
        break;
      default:
        digitalWrite(ledMerah, LOW);
        digitalWrite(ledGlu, LOW);
        digitalWrite(ledIr, LOW);
        break;
    }


    // Format data menjadi string "tipe:nilai"
    String dataString = dataType + ":" + value;

    // Kirim data kembali ke Raspberry Pi melalui serial

    Serial.println(dataString);
  } else {
    digitalWrite(ledMerah, LOW);
    digitalWrite(ledGlu, LOW);
    digitalWrite(ledIr, LOW);
  }
}

String arrayToString(float arr[], int size) {
  String result = "";
  for (int i = 0; i < size; i++) {
    result += String(arr[i], 2);
    if (i < size - 1) {
      result += ",";
    }
  }
  return result;
}