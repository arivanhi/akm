#!/bin/bash

# 1. Jalankan Service Timbangan di background (tanda &)
# Log-nya kita buang ke file terpisah atau stdout agar tidak menumpuk
python ble_scale_service.py &

# 2. Jalankan Web Server Flask di foreground (utama)
python app.py