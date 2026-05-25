import joblib
import pandas as pd
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
import models, database, auth
from pydantic import BaseModel, Field
from typing import List, Annotated
import os


app = FastAPI(
    title="Car Price Prediction API",
    description="API for predicting car prices and managing users.",
    version="1.0.0"
)
models.Base.metadata.create_all(bind=database.engine)

# --- ML Model Integration ---

# Define the path where your model artifacts are stored
# These files should be in the same directory as main.py
MODEL_PATH = '.'

model = None
scaler = None
onehot_columns = None

@app.on_event("startup")
async def load_model_artifacts():
    global model, scaler, onehot_columns
    try:
        model = joblib.load(f'{MODEL_PATH}/model.pkl')
        scaler = joblib.load(f'{MODEL_PATH}/scaler.pkl')
        onehot_columns = joblib.load(f'{MODEL_PATH}/onehot_columns.pkl')
        print("ML Model, Scaler, and One-Hot Columns loaded successfully.")
    except FileNotFoundError as e:
        print(f"Error loading ML model artifacts: {e}. Please ensure model.pkl, scaler.pkl, and onehot_columns.pkl are in the {MODEL_PATH} directory.")
        raise RuntimeError("Failed to load ML model artifacts. Check file paths.")
    except Exception as e:
        print(f"An unexpected error occurred while loading model artifacts: {e}")
        raise RuntimeError("Failed to load ML model artifacts.")

# Define the input features based on your training data
ORIGINAL_FEATURES = ['model', 'year', 'transmission', 'mileage', 'fuelType', 'tax', 'mpg', 'engineSize']
NUMERICAL_FEATURES = ['year', 'mileage', 'tax', 'mpg', 'engineSize']
CATEGORICAL_FEATURES = ['model', 'transmission', 'fuelType']

# Pydantic model for prediction input with validation
class CarFeatures(BaseModel):
    model: str = Field(..., example="Fiesta")
    year: int = Field(..., ge=1990, le=2025, example=2019)
    transmission: str = Field(..., example="Manual")
    mileage: int = Field(..., ge=0, example=15000)
    fuelType: str = Field(..., example="Petrol")
    tax: int = Field(..., ge=0, example=145)
    mpg: float = Field(..., ge=0.0, example=45.0)
    engineSize: float = Field(..., ge=0.0, example=1.0)

@app.get("/")
async def health_check():
    return {"status": "ok", "message": "FastAPI server is running"}

@app.post("/predict")
async def predict_car_price(features: CarFeatures):
    if model is None or scaler is None or onehot_columns is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="ML model not loaded. Server is not ready for predictions.")

    try:
        # Convert input features to a DataFrame
        input_df = pd.DataFrame([features.dict()])

        # Apply one-hot encoding, matching the training pipeline
        # Create dummy variables for categorical columns in the input
        input_encoded = pd.get_dummies(input_df, columns=CATEGORICAL_FEATURES, drop_first=True)

        # Align columns with the training data\'s onehot_columns
        # This handles cases where input might miss some categories or have extra ones
        missing_cols = set(onehot_columns) - set(input_encoded.columns)
        for c in missing_cols:
            input_encoded[c] = 0 # Add missing columns with 0

        # Ensure the order of columns is the same as during training
        input_encoded = input_encoded[onehot_columns]

        # Convert boolean columns to integer (as done during training with .astype(int))
        for col in input_encoded.select_dtypes(include=['bool']).columns:
            input_encoded[col] = input_encoded[col].astype(int)

        # Apply scaling to numerical features
        input_encoded[NUMERICAL_FEATURES] = scaler.transform(input_encoded[NUMERICAL_FEATURES])

        # Make prediction
        prediction = model.predict(input_encoded)[0]

        return {"predicted_price": round(prediction, 2)}
    except Exception as e:
        # Log the detailed error for debugging purposes (e.g., to a file or monitoring system)
        print(f"Prediction error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Prediction failed due to an internal error: {e}")

# --- User Management Endpoints (Existing Code) ---

class UserCreate(BaseModel):
    username: str
    password: str

@app.post("/register", response_model=auth.Token)
def register(user: UserCreate, db: Session = Depends(database.get_db)):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
    hashed_pw = auth.get_password_hash(user.password)
    new_user = models.User(username=user.username, hashed_password=hashed_pw)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    access_token = auth.create_access_token(data={"sub": new_user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/login", response_model=auth.Token)
def login(user: UserCreate, db: Session = Depends(database.get_db)):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if not db_user or not auth.verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = auth.create_access_token(data={"sub": db_user.username})
    return {"access_token": token, "token_type": "bearer"}

@app.get("/admin/users", dependencies=[Depends(auth.get_current_active_admin_user)]) # Requires admin user
def get_all_users(db: Session = Depends(database.get_db)):
    return db.query(models.User).all()