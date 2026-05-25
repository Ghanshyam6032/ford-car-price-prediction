import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import json

BASE_URL = "http://localhost:8000"

st.set_page_config(page_title="Enterprise App", layout="wide")

if 'token' not in st.session_state:
    st.session_state['token'] = None
if 'is_admin' not in st.session_state:
    st.session_state['is_admin'] = False # Default to not admin

def login_page():
    st.header("Login")
    user = st.text_input("Username")
    pw = st.text_input("Password", type="password")
    if st.button("Login"):
        try:
            res = requests.post(f"{BASE_URL}/login", json={"username": user, "password": pw})
            if res.status_code == 200:
                response_data = res.json()
                st.session_state['token'] = response_data["access_token"]
                st.session_state['is_admin'] = response_data.get("is_admin", False) # Get is_admin status
                st.success("Logged in!")
                st.rerun()
            else:
                st.error(f"Login failed: {res.json().get('detail', 'Unknown error')}")
        except requests.exceptions.ConnectionError:
            st.error(f"Could not connect to the backend. Is the FastAPI server running on {BASE_URL}?")
        except Exception as e:
            st.error(f"An unexpected error occurred during login: {e}")

def dashboard():
    st.title("User Dashboard")
    st.write("Welcome to your data center.")

    # Removed File Upload section

    st.markdown("--- ")
    st.header("Car Price Prediction")

    # Conditionally display prediction form based on is_admin status
    if st.session_state['is_admin']:
        st.warning("Admin users cannot perform predictions.")
    else:
        # Input form for car features with improved layout
        with st.form("car_prediction_form"):
            st.write("Enter car features to predict its price:")

            col1, col2, col3 = st.columns(3)
            with col1:
                model_options = ['Fiesta', 'Focus', 'Puma', 'Kuga', 'EcoSport', 'C-MAX', 'Mondeo', 'Ka+', 'Tourneo Custom', 'S-MAX', 'B-MAX', 'Edge', 'Tourneo Connect', 'Grand C-MAX', 'KA', 'Galaxy', 'Mustang', 'Grand Tourneo Connect', 'Fusion', 'Ranger', 'Streetka', 'Escort', 'Transit Tourneo']
                model = st.selectbox("Model", model_options)
                year = st.number_input("Year", min_value=1996, max_value=2024, value=2018)
                transmission = st.selectbox("Transmission", ['Automatic', 'Manual', 'Semi-Auto'])
            with col2:
                mileage = st.number_input("Mileage", min_value=0, value=20000, help="Total miles driven")
                fuelType = st.selectbox("Fuel Type", ['Petrol', 'Diesel', 'Hybrid', 'Electric', 'Other'])
                tax = st.number_input("Tax (£)", min_value=0, value=150)
            with col3:
                mpg = st.number_input("MPG (Miles Per Gallon)", min_value=0.0, value=50.0, format="%.1f")
                engineSize = st.number_input("Engine Size (Liters)", min_value=0.0, value=1.0, format="%.1f")

            predict_button = st.form_submit_button("Predict Price")

            if predict_button:
                # Prepare data for API request
                car_data = {
                    "model": model,
                    "year": year,
                    "transmission": transmission,
                    "mileage": mileage,
                    "fuelType": fuelType,
                    "tax": tax,
                    "mpg": mpg,
                    "engineSize": engineSize,
                }

                try:
                    # Use JWT for authentication
                    headers = {"Authorization": f"Bearer {st.session_state['token']}"}
                    response = requests.post(f"{BASE_URL}/predict", json=car_data, headers=headers)

                    if response.status_code == 200:
                        predicted_price = response.json()["predicted_price"]
                        st.success(f"Predicted Car Price: £{predicted_price:,.2f}")
                    elif response.status_code == 401:
                        st.error(f"Prediction failed: Authentication error. Please log in again.")
                        st.session_state['token'] = None # Clear invalid token
                        st.session_state['is_admin'] = False
                        st.rerun()
                    elif response.status_code == 403:
                        st.error(f"Prediction failed: {response.json().get('detail', 'Access Denied')}")
                    else:
                        st.error(f"Error from prediction service ({response.status_code}): {response.json().get('detail', 'Unknown error')}")
                except requests.exceptions.ConnectionError:
                    st.error(f"Could not connect to the prediction service. Is the FastAPI backend running on {BASE_URL}?")
                except Exception as e:
                    st.error(f"An unexpected error occurred: {e}")

def analytics_page():
    st.title("Admin Analytics Dashboard")
    st.write("This panel is ONLY for monitoring system users and analytics. No prediction features are allowed here.")

    if not st.session_state['is_admin']:
        st.error("Access Denied: Admin privileges required.")
        return

    try:
        headers = {"Authorization": f"Bearer {st.session_state['token']}"}
        response = requests.get(f"{BASE_URL}/admin/users", headers=headers)
        
        if response.status_code == 200:
            users_data = response.json()
            df_users = pd.DataFrame(users_data)

            # Add a 'Role' column
            df_users['Role'] = df_users['is_admin'].apply(lambda x: 'Admin' if x else 'User')

            # Clean up columns for display
            display_columns = ['id', 'username', 'Role', 'Registration Time'] # Assuming 'Registration Time' will be added in backend or is 'timestamp'
            # Filter to only relevant columns and rename for display
            df_users_display = df_users[['id', 'username', 'Role']].copy()

            # System Overview Cards
            st.subheader("System Overview")
            col_metrics1, col_metrics2 = st.columns(2)
            with col_metrics1:
                st.metric(label="Total Users", value=len(df_users))
            with col_metrics2:
                st.metric(label="Total Admins", value=df_users['is_admin'].sum())

            st.subheader("User Information Table")
            st.dataframe(df_users_display, use_container_width=True)

        elif response.status_code == 401:
            st.error("Authentication error. Please log in again.")
            st.session_state['token'] = None
            st.session_state['is_admin'] = False
            st.rerun()
        elif response.status_code == 403:
            st.error(f"Access Denied: {response.json().get('detail', 'Not enough permissions')}")
        else:
            st.error(f"Error fetching users ({response.status_code}): {response.json().get('detail', 'Unknown error')}")
    except requests.exceptions.ConnectionError:
        st.error(f"Could not connect to the backend. Is the FastAPI server running on {BASE_URL}?")
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")


# Navigation
if not st.session_state['token']:
    tab1, tab2 = st.tabs(["Login", "Register"])
    with tab1: login_page()
    with tab2:
        st.header("Register")
        u = st.text_input("New Username")
        p = st.text_input("New Password", type="password")
        if st.button("Sign Up"):
            try:
                res = requests.post(f"{BASE_URL}/register", json={"username":u, "password":p})
                if res.status_code == 200:
                    st.success("Registration successful! You can now log in.")
                else:
                    st.error(f"Registration failed: {res.json().get('detail', 'Unknown error')}")
            except requests.exceptions.ConnectionError:
                st.error(f"Could not connect to the backend. Is the FastAPI server running on {BASE_URL}?")
            except Exception as e:
                st.error(f"An unexpected error occurred during registration: {e}")
else:
    menu = ["Dashboard"]
    if st.session_state['is_admin']:
        menu.append("Analytics") # Only add Analytics for admin users
    menu.append("Logout")

    choice = st.sidebar.selectbox("Menu", menu)
    if choice == "Dashboard": dashboard()
    elif choice == "Analytics":
        analytics_page() # Call the new analytics page function
    elif choice == "Logout":
        st.session_state['token'] = None
        st.session_state['is_admin'] = False
        st.success("Logged out successfully.")
        st.rerun()