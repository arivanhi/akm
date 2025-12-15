#include <Wire.h>
#include "AS726X.h"
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEScan.h>
#include <BLEAdvertisedDevice.h>

// ==========================================
// --- KONFIGURASI PIN & SENSOR ---
// ==========================================
#define ledMerah 17
#define ledIr 2
#define ledGlu 16
#define photoDioda 4

AS726X sensor;

// ==========================================
// --- KONFIGURASI BLE OMRON ---
// ==========================================
// Ganti dengan MAC Address Omron Anda (Huruf kecil semua)
String omronAddress = "00:5f:bf:bd:d0:d8"; 

static BLEUUID serviceUUID("1810"); // Blood Pressure Service
static BLEUUID charUUID("2A35");    // BP Measurement Characteristic

// Variabel Kontrol BLE
boolean bleActive = false;      // Status apakah mode Tensimeter sedang aktif
boolean doConnect = false;
boolean connected = false;
boolean dataReceived = false;   // Penanda data sudah dapat
BLERemoteCharacteristic* pRemoteCharacteristic;
BLEAdvertisedDevice* myDevice;

// Variabel Global Kontrol Utama
int currentMeasurementType = 0; // 0=Idle, 1=Kol, 2=AU, 3=Glu, 4=Tensi

// ==========================================
// --- FUNGSI UTILITY BLE ---
// ==========================================

// Decode SFloat (Standar IEEE-11073)
float decodeSFloat(uint8_t* data, int startIndex) {
  uint16_t raw = data[startIndex] | (data[startIndex + 1] << 8);
  int16_t mantissa = raw & 0x0FFF;
  int8_t exponent = (raw >> 12) & 0x0F;
  if (exponent >= 0x08) exponent = -((0x0F + 1) - exponent);
  if (mantissa >= 0x0800) mantissa = -((0xFFF + 1) - mantissa);
  return mantissa * pow(10, exponent);
}

// Callback saat data masuk dari Omron
static void notifyCallback(BLERemoteCharacteristic* pBLERemoteCharacteristic, uint8_t* pData, size_t length, bool isNotify) {
    if (length < 2) return;

    uint8_t flags = pData[0];
    bool iskPa = flags & 0x01;
    bool hasTimestamp = flags & 0x02;
    bool hasPulse = flags & 0x04;

    int index = 1;
    float sys = decodeSFloat(pData, index); index+=2;
    float dia = decodeSFloat(pData, index); index+=2;
    float map = decodeSFloat(pData, index); index+=2;

    if (hasTimestamp) index += 7;

    float pulse = 0;
    if (hasPulse) pulse = decodeSFloat(pData, index);

    // Format kirim ke Python: "tensi:sys,dia,pulse"
    String output = "tensi:" + String(sys, 0) + "," + String(dia, 0) + "," + String(pulse, 0);
    Serial.println(output);

    // Tandai selesai agar loop memutus koneksi
    dataReceived = true; 
}

// Security Callback (Auto Pair)
class MySecurity : public BLESecurityCallbacks {
  uint32_t onPassKeyRequest(){ return 000000; }
  void onPassKeyNotify(uint32_t pass_key){}
  bool onConfirmPIN(uint32_t pass_key){ return true; }
  bool onSecurityRequest(){ return true; }
  void onAuthenticationComplete(esp_ble_auth_cmpl_t cmpl){}
};

// Client Callback
class MyClientCallback : public BLEClientCallbacks {
  void onConnect(BLEClient* pclient) {}
  void onDisconnect(BLEClient* pclient) {
    connected = false;
    // Serial.println("BLE Disconnected");
  }
};

// Scan Callback
class MyAdvertisedDeviceCallbacks: public BLEAdvertisedDeviceCallbacks {
  void onResult(BLEAdvertisedDevice advertisedDevice) {
    String devAddr = advertisedDevice.getAddress().toString().c_str();
    devAddr.toLowerCase(); 
    if (devAddr == omronAddress) {
      BLEDevice::getScan()->stop();
      myDevice = new BLEAdvertisedDevice(advertisedDevice);
      doConnect = true;
    }
  }
};

// Fungsi Koneksi BLE
bool connectToOmron() {
    BLEClient* pClient  = BLEDevice::createClient();
    pClient->setClientCallbacks(new MyClientCallback());

    if (!pClient->connect(myDevice)) return false;
    pClient->secureConnection();

    BLERemoteService* pRemoteService = pClient->getService(serviceUUID);
    if (pRemoteService == nullptr) {
      pClient->disconnect();
      return false;
    }

    pRemoteCharacteristic = pRemoteService->getCharacteristic(charUUID);
    if (pRemoteCharacteristic == nullptr) {
      pClient->disconnect();
      return false;
    }

    // Force Enable Indication (Magic Fix)
    BLERemoteDescriptor* p2902 = pRemoteCharacteristic->getDescriptor(BLEUUID((uint16_t)0x2902));
    if (p2902 != nullptr) {
      uint8_t val[] = {0x02, 0x00}; 
      p2902->writeValue(val, 2, true);
    }

    if(pRemoteCharacteristic->canIndicate() || pRemoteCharacteristic->canNotify()) {
      pRemoteCharacteristic->registerForNotify(notifyCallback);
    }

    connected = true;
    return true;
}

// ==========================================
// --- FUNGSI SENSOR OPTIK (AS726X) ---
// ==========================================

void TCA9548A(uint8_t bus) {
  Wire.beginTransmission(0x70);
  Wire.write(1 << bus);
  Wire.endTransmission();
}

int glukosa() {
  int read;
  digitalWrite(ledGlu, HIGH);
  delay(50);
  read = analogRead(photoDioda);
  return read;
}

String asamUrat() {
  digitalWrite(ledMerah, HIGH);
  TCA9548A(2);
  sensor.takeMeasurements();
  String data = String(sensor.getCalibratedViolet()) + "," +
                String(sensor.getCalibratedBlue()) + "," +
                String(sensor.getCalibratedGreen()) + "," +
                String(sensor.getCalibratedYellow()) + "," +
                String(sensor.getCalibratedOrange()) + "," +
                String(sensor.getCalibratedRed());
  return data;
}

String kolesterol() {
  digitalWrite(ledIr, HIGH);
  TCA9548A(3);
  sensor.takeMeasurements();
  float r = sensor.getCalibratedR();
  return String(r);
}

// ==========================================
// --- SETUP & LOOP ---
// ==========================================

void setup() {
  Wire.begin();
  Serial.begin(115200);
  analogReadResolution(8); // Untuk Glukosa

  pinMode(ledMerah, OUTPUT);
  pinMode(ledIr, OUTPUT);
  pinMode(ledGlu, OUTPUT);

  // Init Sensor Optik
  TCA9548A(2); sensor.begin();
  TCA9548A(3); sensor.begin();

  // Init BLE (Tapi belum scan)
  BLEDevice::init("ESP32_Health");
  BLESecurity *pSecurity = new BLESecurity();
  pSecurity->setAuthenticationMode(ESP_LE_AUTH_REQ_SC_BOND);
  pSecurity->setCapability(ESP_IO_CAP_IO);
  pSecurity->setInitEncryptionKey(ESP_BLE_ENC_KEY_MASK | ESP_BLE_ID_KEY_MASK);
  pSecurity->setRespEncryptionKey(ESP_BLE_ENC_KEY_MASK | ESP_BLE_ID_KEY_MASK);
  BLEDevice::setSecurityCallbacks(new MySecurity());
  
  BLEScan* pBLEScan = BLEDevice::getScan();
  pBLEScan->setAdvertisedDeviceCallbacks(new MyAdvertisedDeviceCallbacks());
  pBLEScan->setActiveScan(true);
  pBLEScan->setInterval(100);
  pBLEScan->setWindow(99);

  Serial.println("ESP32 Ready. Waiting for commands...");
}

void loop() {
  // 1. BACA SERIAL
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    int flag = command.toInt();

    if (flag >= 0 && flag <= 4) {
      currentMeasurementType = flag;
      
      // Reset status BLE jika pindah mode
      if (flag != 4) {
        bleActive = false;
        if(connected) { /* logic disconnect manual jika perlu */ }
      } else {
        // Jika Flag == 4, Reset variabel BLE untuk memulai scan baru
        bleActive = true;
        doConnect = false;
        connected = false;
        dataReceived = false;
        Serial.println("MODE_TENSI_AKTIF"); // Debug info
      }
    }
  }

  // 2. LOGIKA STATE
  if (currentMeasurementType != 0) {
    
    // --- MODE SENSOR OPTIK (1, 2, 3) ---
    if (currentMeasurementType >= 1 && currentMeasurementType <= 3) {
       String dataType, value;
       switch (currentMeasurementType) {
          case 1: dataType = "cholesterol"; value = kolesterol(); break;
          case 2: dataType = "asam_urat"; value = asamUrat(); break;
          case 3: dataType = "gula_darah"; value = String(glukosa()); delay(100); break;
       }
       Serial.println(dataType + ":" + value);
    }
    
    // --- MODE TENSIMETER (4) ---
    else if (currentMeasurementType == 4 && bleActive) {
       // Jika data sudah diterima, kirim sinyal stop/reset dan matikan mode
       if (dataReceived) {
          bleActive = false;
          currentMeasurementType = 0; // Kembali ke Idle
          // Kita tidak perlu kirim apa-apa lagi karena data sudah dikirim di notifyCallback
          // Cukup pastikan scan berhenti
          return; 
       }

       // Logika Koneksi BLE
       if (doConnect) {
          if (connectToOmron()) {
             // Serial.println("Connected to Omron! Press Sync Button.");
          } else {
             // Serial.println("Connect Failed");
          }
          doConnect = false;
       }

       // Jika belum konek dan belum dapat data, lakukan SCAN
       if (!connected) {
          BLEScan* pBLEScan = BLEDevice::getScan();
          pBLEScan->start(1, false); // Scan singkat 1 detik
          pBLEScan->clearResults();
       }
    }

  } else {
    // IDLE: Matikan semua LED
    digitalWrite(ledMerah, LOW);
    digitalWrite(ledGlu, LOW);
    digitalWrite(ledIr, LOW);
  }
}