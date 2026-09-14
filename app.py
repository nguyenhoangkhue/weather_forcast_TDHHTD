import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time

CITIES = {
    "Hà Nội": {"lat": 21.0285, "lon": 105.8542},
    "TP. Hồ Chí Minh": {"lat": 10.8231, "lon": 106.6297},
    "Đà Nẵng": {"lat": 16.0544, "lon": 108.2022},
    "Hải Phòng": {"lat": 20.8449, "lon": 106.6881},
    "Cần Thơ": {"lat": 10.0452, "lon": 105.7469},
    "Nha Trang": {"lat": 12.2388, "lon": 109.1967},
    "Đà Lạt": {"lat": 11.9404, "lon": 108.4583},
    "Huế": {"lat": 16.4637, "lon": 107.5909}
}

st.set_page_config(page_title="Dự báo thời tiết Việt Nam", layout="wide")
st.title("🌤️ Ứng dụng Thời tiết & Bức xạ mặt trời tại Việt Nam")

st.sidebar.header("Tùy chỉnh tham số")

input_mode = st.sidebar.radio("Phương thức nhập vị trí:", ["Chọn Tỉnh/Thành phố", "Nhập tọa độ tùy chỉnh"])

if input_mode == "Chọn Tỉnh/Thành phố":
    selected_city = st.sidebar.selectbox("Chọn Tỉnh/Thành phố:", list(CITIES.keys()))
    lat = CITIES[selected_city]["lat"]
    lon = CITIES[selected_city]["lon"]
    location_name = selected_city
else:
    lat_input = st.sidebar.text_input("Vĩ độ (Latitude):", value="21.0285")
    lon_input = st.sidebar.text_input("Kinh độ (Longitude):", value="105.8542")
    try:
        lat = float(lat_input)
        lon = float(lon_input)
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            st.sidebar.error("Tọa độ không hợp lệ! Vĩ độ: -90~90, Kinh độ: -180~180")
            st.stop()
        location_name = f"Tọa độ ({lat}, {lon})"
    except ValueError:
        st.sidebar.error("Vui lòng nhập số hợp lệ!")
        st.stop()

mode = st.sidebar.radio("Chọn khoảng thời gian dữ liệu:", ["Hiện tại & Dự báo", "Dữ liệu Quá khứ", "Kết hợp (Quá khứ + Dự báo)"])

forecast_days = 7
archive_days = 7

if mode in ["Hiện tại & Dự báo", "Kết hợp (Quá khứ + Dự báo)"]:
    forecast_days = st.sidebar.slider("Số ngày dự báo:", min_value=1, max_value=16, value=7)

if mode in ["Dữ liệu Quá khứ", "Kết hợp (Quá khứ + Dự báo)"]:
    archive_days = st.sidebar.slider("Số ngày dữ liệu quá khứ:", min_value=1, max_value=90, value=7)

granularity = st.sidebar.selectbox("Khung thời gian hiển thị:", ["Theo giờ (Hourly)", "Theo ngày (Daily)"])

@st.cache_data(ttl=3600)
def fetch_forecast(lat, lon, forecast_days):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ["temperature_2m", "relative_humidity_2m"],
        "hourly": ["temperature_2m", "relative_humidity_2m", "shortwave_radiation"],
        "daily": ["temperature_2m_max", "temperature_2m_min", "shortwave_radiation_sum"],
        "timezone": "Asia/Bangkok",
        "forecast_days": forecast_days
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    return None

@st.cache_data(ttl=3600)
def fetch_archive(lat, lon, start_date, end_date):
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ["temperature_2m", "relative_humidity_2m", "shortwave_radiation"],
        "daily": ["temperature_2m_max", "temperature_2m_min", "shortwave_radiation_sum"],
        "timezone": "Asia/Bangkok"
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    return None

def merge_hourly(base, overlay):
    result = {"time": [], "temperature_2m": [], "relative_humidity_2m": [], "shortwave_radiation": []}
    for key in ["time", "temperature_2m", "relative_humidity_2m", "shortwave_radiation"]:
        if key in overlay and overlay[key]:
            result[key].extend(overlay[key])
        if key in base and base[key]:
            result[key].extend(base[key])
    return result

def merge_daily(base, overlay):
    result = {"time": [], "temperature_2m_max": [], "temperature_2m_min": [], "shortwave_radiation_sum": []}
    for key in ["time", "temperature_2m_max", "temperature_2m_min", "shortwave_radiation_sum"]:
        if key in overlay and overlay[key]:
            result[key].extend(overlay[key])
        if key in base and base[key]:
            result[key].extend(base[key])
    return result

@st.cache_data(ttl=900)
def fetch_forecast_15min(lat, lon):
    now = datetime.now()
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "minutely_15": ["temperature_2m", "relative_humidity_2m", "shortwave_radiation"],
        "timezone": "Asia/Bangkok"
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        minutely = data.get("minutely_15", {})
        if minutely and "time" in minutely:
            filtered = {"time": [], "temperature_2m": [], "relative_humidity_2m": [], "shortwave_radiation": []}
            for i in range(len(minutely["time"])):
                t = datetime.fromisoformat(minutely["time"][i].replace("Z", "+00:00")).replace(tzinfo=None)
                if t >= now:
                    filtered["time"].append(minutely["time"][i])
                    filtered["temperature_2m"].append(minutely["temperature_2m"][i])
                    filtered["relative_humidity_2m"].append(minutely["relative_humidity_2m"][i])
                    filtered["shortwave_radiation"].append(minutely["shortwave_radiation"][i])
                if len(filtered["time"]) >= 24:
                    break
            return filtered
        return minutely
    return None

def get_weather_icon(temp, radiation):
    if radiation > 200:
        return "☀️"
    elif radiation > 100:
        return "⛅"
    elif radiation > 50:
        return "🌤️"
    elif temp < 20:
        return "🌧️"
    return "☁️"

today = datetime.now().date()
data = None
forecast_data = None
archive_data = None

if mode == "Hiện tại & Dự báo":
    forecast_data = fetch_forecast(lat, lon, forecast_days)
    data = forecast_data
elif mode == "Dữ liệu Quá khứ":
    end_date = today - timedelta(days=1)
    start_date = end_date - timedelta(days=archive_days - 1)
    archive_data = fetch_archive(lat, lon, str(start_date), str(end_date))
    data = archive_data
elif mode == "Kết hợp (Quá khứ + Dự báo)":
    forecast_data = fetch_forecast(lat, lon, forecast_days)
    end_date = today - timedelta(days=1)
    start_date = end_date - timedelta(days=archive_days - 1)
    archive_data = fetch_archive(lat, lon, str(start_date), str(end_date))
    if forecast_data and archive_data:
        data = {
            "current": forecast_data.get("current"),
            "hourly": merge_hourly(forecast_data.get("hourly", {}), archive_data.get("hourly", {})),
            "daily": merge_daily(forecast_data.get("daily", {}), archive_data.get("daily", {}))
        }
    else:
        data = forecast_data or archive_data

if data:
    st.subheader(f"📌 Thời tiết tại {location_name}")

    if "current" in data:
        col1, col2, col3 = st.columns(3)
        col1.metric("Nhiệt độ hiện tại", f"{data['current']['temperature_2m']} °C")
        col2.metric("Độ ẩm hiện tại", f"{data['current']['relative_humidity_2m']} %")

        if "hourly" in data and "shortwave_radiation" in data["hourly"]:
            current_hour = datetime.now().hour
            rad_val = data["hourly"]["shortwave_radiation"][current_hour] if current_hour < len(data["hourly"]["shortwave_radiation"]) else None
            col3.metric("Bức xạ mặt trời", f"{rad_val} W/m²" if rad_val is not None else "N/A")
        else:
            col3.metric("Bức xạ mặt trời", "N/A")

    st.markdown("---")
    
    st.subheader("⏱️ Dự báo theo 15 phút (tự động cập nhật)")
    
    minutely_data = fetch_forecast_15min(lat, lon)
    
    if minutely_data and "time" in minutely_data and len(minutely_data["time"]) > 0:
        now = datetime.now()
        minutes_left = 15 - (now.minute % 15)
        
        col_info1, col_info2 = st.columns(2)
        with col_info1:
            st.info(f"📅 Dữ liệu từ: **{now.strftime('%H:%M')}**")
        with col_info2:
            st.info(f"🔄 Cập nhật sau: **{minutes_left} phút**")
        
        display_count = min(len(minutely_data["time"]), 12)
        
        filtered_times = []
        filtered_temps = []
        filtered_humidity = []
        filtered_radiation = []
        for i in range(display_count):
            time_dt = datetime.fromisoformat(minutely_data["time"][i].replace("Z", "+00:00"))
            filtered_times.append(time_dt.strftime("%H:%M"))
            filtered_temps.append(minutely_data["temperature_2m"][i])
            filtered_humidity.append(minutely_data["relative_humidity_2m"][i])
            filtered_radiation.append(minutely_data["shortwave_radiation"][i])
        
        cols = st.columns(6)
        for i in range(display_count):
            with cols[i % 6]:
                st.markdown(f"""
                <div style="background: white; border-radius: 10px; padding: 15px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.06); border: 1px solid #e2e8f0; margin-bottom: 10px;">
                    <div style="font-size: 0.9rem; font-weight: 600; color: #1565c0; margin-bottom: 8px;">{filtered_times[i]}</div>
                    <div style="font-size: 1.8rem; margin-bottom: 5px;">{get_weather_icon(filtered_temps[i], filtered_radiation[i])}</div>
                    <div style="font-size: 1.3rem; font-weight: 700; color: #2c3e50;">{filtered_temps[i]:.1f}°C</div>
                    <div style="font-size: 0.8rem; color: #7f8c8d; margin-top: 4px;">💧 {filtered_humidity[i]:.0f}%</div>
                    <div style="font-size: 0.8rem; color: #7f8c8d;">☀️ {filtered_radiation[i]:.0f} W/m²</div>
                </div>
                """, unsafe_allow_html=True)
        
        df_15min = pd.DataFrame({
            "Thời gian": filtered_times,
            "Nhiệt độ (°C)": filtered_temps,
            "Độ ẩm (%)": filtered_humidity,
            "Bức xạ (W/m²)": filtered_radiation
        })
        
        st.line_chart(df_15min.set_index("Thời gian")[["Nhiệt độ (°C)", "Độ ẩm (%)"]])
        st.area_chart(df_15min.set_index("Thời gian")["Bức xạ (W/m²)"])
    else:
        st.warning("Không thể tải dữ liệu dự báo 15 phút")
    
    st.markdown("---")
    st.subheader(f"📊 Dữ liệu chi tiết")

    if granularity == "Theo giờ (Hourly)" and "hourly" in data:
        df = pd.DataFrame({
            "Thời gian": data["hourly"]["time"],
            "Nhiệt độ (°C)": data["hourly"]["temperature_2m"],
            "Độ ẩm (%)": data["hourly"]["relative_humidity_2m"],
            "Bức xạ mặt trời (W/m²)": data["hourly"]["shortwave_radiation"]
        })
        df["Thời gian"] = pd.to_datetime(df["Thời gian"])

        st.line_chart(df.set_index("Thời gian")[["Nhiệt độ (°C)", "Độ ẩm (%)"]])
        st.area_chart(df.set_index("Thời gian")["Bức xạ mặt trời (W/m²)"])

        st.dataframe(df, use_container_width=True)

        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Tải file CSV (Theo giờ)",
            data=csv,
            file_name=f"thoi_tiet_hourly_{today}.csv",
            mime="text/csv"
        )

    elif granularity == "Theo ngày (Daily)" and "daily" in data:
        df = pd.DataFrame({
            "Ngày": data["daily"]["time"],
            "Nhiệt độ Cao nhất (°C)": data["daily"]["temperature_2m_max"],
            "Nhiệt độ Thấp nhất (°C)": data["daily"]["temperature_2m_min"],
            "Tổng Bức xạ mặt trời (MJ/m²)": data["daily"]["shortwave_radiation_sum"]
        })

        st.line_chart(df.set_index("Ngày")[["Nhiệt độ Cao nhất (°C)", "Nhiệt độ Thấp nhất (°C)"]])
        st.bar_chart(df.set_index("Ngày")["Tổng Bức xạ mặt trời (MJ/m²)"])

        st.dataframe(df, use_container_width=True)

        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Tải file CSV (Theo ngày)",
            data=csv,
            file_name=f"thoi_tiet_daily_{today}.csv",
            mime="text/csv"
        )

else:
    st.error("Không thể lấy dữ liệu từ API. Vui lòng kiểm tra lại kết nối hoặc tham số chọn!")

st.markdown("---")

st.markdown("---")
st.caption("⏱️ Dự báo 15 phút tự động cập nhật mỗi 15 phút")

now = datetime.now()
minutes_left = 15 - (now.minute % 15)
st.info(f"🔄 Cập nhật tiếp theo sau: **{minutes_left} phút**")

time.sleep(1)
if st.button("🔄 Bật tự động cập nhật", key="auto_refresh"):
    st.rerun()
