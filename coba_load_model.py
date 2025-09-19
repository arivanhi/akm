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

print("Loading model xboost and predictions from saved files...")
load_model_path = 'model/xgboost_model.json'
xgb_model = xgb.XGBClassifier()
xgb_model.load_model(load_model_path)
xgb_predictions_encoded = xgb_model.predict(X_train)
xgb_predictions = label_encoder.inverse_transform(xgb_predictions_encoded)
xgb_accuracy = accuracy_score(Y_train, xgb_predictions)
print("XGBoost Accuracy (loaded model):", xgb_accuracy)

print("Loading KNN predictions from saved file...")
load_model_path = 'model/knn_predictions.npy'
knn_predictions = np.load(load_model_path)
knn_accuracy = accuracy_score(Y_train, knn_predictions)
print("KNN Accuracy (loaded predictions):", knn_accuracy)
