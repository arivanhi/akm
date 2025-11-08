import pandas as pd
import numpy as np
import tensorflow as tf
import os

model = 'model_kolesterol_VIS_2.h5'
data = 'data/adc_kolesterol_v2.csv'

df = pd.read_csv(data,header=0)
test_data = df.iloc[150, 0:20].values
print(f"test data: {test_data}")

load_model_path = os.path.join('model', model)
loaded_model = tf.keras.models.load_model(load_model_path, compile=False)
loaded_model.summary()

print(f"shape model input: {loaded_model.input_shape}")
print(f"shape model output: {loaded_model.output_shape}")

prediksi = loaded_model.predict(test_data.reshape(1, -1)) * 10.0
print(f"prediksi kolesterol: {prediksi[0][0]}")
