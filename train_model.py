import xgboost as xgb
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import confusion_matrix, accuracy_score

file_path = 'data ADC Glukosa.xlsx'
sheet_name = 'Sheet1'
df = pd.read_excel(file_path, sheet_name=sheet_name)

df_X = pd.read_excel(file_path, sheet_name=sheet_name, usecols='A:PD', header=None, skiprows=1, nrows=250)
df_y = pd.read_excel(file_path, sheet_name=sheet_name, usecols='A:PD', header=None, nrows=1)

X_train = df_X.to_numpy()
X_train = np.transpose(X_train) 

Y_train = df_y.to_numpy().flatten()

label_encoder = LabelEncoder()
Y_train_encoded = label_encoder.fit_transform(Y_train)

print("Dimensi X_train:", X_train.shape)
print("Dimensi Y_train:", Y_train.shape)

print("Data X_train (first 5 rows):")
print(X_train[:5])
print("Data Y_train (first 5 elements):")
print(Y_train[:5])

knn = KNeighborsClassifier(n_neighbors=3)
knn.fit(X_train, Y_train)
knn_predictions = knn.predict(X_train)
knn_accuracy = accuracy_score(Y_train, knn_predictions)
knn_cm = confusion_matrix(Y_train, knn_predictions)
print("KNN Accuracy:", knn_accuracy)
# print("KNN Confusion Matrix:\n", knn_cm)
save_path = 'model/knn_predictions.npy'
np.save(save_path, knn_predictions)
print(f"Prediksi KNN disimpan di {save_path}")

xgb_model = xgb.XGBClassifier()
xgb_model.fit(X_train, Y_train_encoded)
xgb_predictions_encoded = xgb_model.predict(X_train)
xgb_predictions = label_encoder.inverse_transform(xgb_predictions_encoded)
xgb_accuracy = accuracy_score(Y_train, xgb_predictions)
xgb_cm = confusion_matrix(Y_train, xgb_predictions)
print("XGBoost Accuracy:", xgb_accuracy)
# print("XGBoost Confusion Matrix:\n", xgb_cm)
save_path = 'model/xgboost_model.json'
xgb_model.save_model(save_path)
print(f"Model XGBoost disimpan di {save_path}")
