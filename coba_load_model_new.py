import xgboost as xgb
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import confusion_matrix, accuracy_score

file_path = 'data/adc_asam_urat.csv'
df = pd.read_csv(file_path)
X_train = df[1:].to_numpy()
X_train = np.round(X_train).astype(int)
X_train = np.transpose(X_train)
y_train = df[0:1].to_numpy().flatten()
y_train = np.round(y_train).astype(int)

label_encoder = LabelEncoder()
y_train_encoded = label_encoder.fit_transform(y_train)

print("Loading model xboost and predictions from saved files...")
load_model_path = 'model/xgboost_asam_urat_model.json'
xgb_model = xgb.XGBClassifier()
xgb_model.load_model(load_model_path)
xgb_predictions_encoded = xgb_model.predict(X_train)
print(xgb_predictions_encoded)
xgb_predictions = label_encoder.inverse_transform(xgb_predictions_encoded)
xgb_accuracy = accuracy_score(y_train, xgb_predictions)
print("XGBoost Accuracy (loaded model):", xgb_accuracy)

print("Loading KNN predictions from saved file...")
load_model_path = 'model/knn_asam_urat_predictions.npy'
knn_predictions = np.load(load_model_path)
knn_accuracy = accuracy_score(y_train, knn_predictions)
print("KNN Accuracy (loaded predictions):", knn_accuracy)

asam_urat = (xgb_predictions_encoded[0]+knn_predictions[0])/2
print("prediksi asam urat: ", asam_urat)

file_path = 'data/adc_kolesterol.csv'
df = pd.read_csv(file_path)
X_train = df[1:].to_numpy()
X_train = np.round(X_train).astype(int)
X_train = np.transpose(X_train)
y_train = df[0:1].to_numpy().flatten()
y_train = np.round(y_train).astype(int)

label_encoder = LabelEncoder()
y_train_encoded = label_encoder.fit_transform(y_train)

print("Loading model xboost and predictions from saved files...")
load_model_path = 'model/xgboost_kolesterol_model.json'
xgb_model = xgb.XGBClassifier()
xgb_model.load_model(load_model_path)
xgb_predictions_encoded = xgb_model.predict(X_train)
xgb_predictions = label_encoder.inverse_transform(xgb_predictions_encoded)
xgb_accuracy = accuracy_score(y_train, xgb_predictions)
print("XGBoost Accuracy (loaded model):", xgb_accuracy)

print("Loading KNN predictions from saved file...")
load_model_path = 'model/knn_kolesterol_predictions.npy'
knn_predictions = np.load(load_model_path)
knn_accuracy = accuracy_score(y_train, knn_predictions)
print("KNN Accuracy (loaded predictions):", knn_accuracy)

kolesterol = (xgb_predictions_encoded[0]+knn_predictions[0])/2
print("prediksi kolesterol: ", kolesterol)