import xgboost as xgb
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.metrics import confusion_matrix, accuracy_score


file_path = 'data/adc_kolesterol_v2.csv'
df = pd.read_csv(file_path)
X_train = df.iloc[:, 0:20].to_numpy()
X_train = np.round(X_train).astype(int)
# X_train = np.transpose(X_train)
y_train = df.iloc[:, 20:].to_numpy()
y_train = np.round(y_train).astype(int)

print("Data X_train (first 5 rows):")
print(X_train[:5])
print("Data Y_train (first 5 elements):") 
print(y_train[:5])


label_encoder = LabelEncoder()
y_train_encoded = label_encoder.fit_transform(y_train)

print("Dimensi X_train:", X_train.shape)
print("Dimensi Y_train:", y_train.shape)

knn = KNeighborsClassifier(n_neighbors=1)
knn.fit(X_train, y_train)
knn_predictions = knn.predict(X_train)
knn_accuracy = accuracy_score(y_train, knn_predictions)
knn_cm = confusion_matrix(y_train, knn_predictions)
print("KNN Accuracy:", knn_accuracy)
# print("KNN Confusion Matrix:\n", knn_cm)
save_path = 'model/knn_kolesterol2_predictions.npy'
np.save(save_path, knn_predictions)
print(f"Prediksi KNN disimpan di {save_path}")

xgb_model = xgb.XGBClassifier()
xgb_model.fit(X_train, y_train_encoded)
xgb_predictions_encoded = xgb_model.predict(X_train)
xgb_predictions = label_encoder.inverse_transform(xgb_predictions_encoded)
xgb_accuracy = accuracy_score(y_train, xgb_predictions)
xgb_cm = confusion_matrix(y_train, xgb_predictions)
print("XGBoost Accuracy:", xgb_accuracy)
# print("XGBoost Confusion Matrix:\n", xgb_cm)
save_path = 'model/xgboost_kolesterol2_model.json'
xgb_model.save_model(save_path)
print(f"Model XGBoost disimpan di {save_path}")

