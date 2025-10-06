import streamlit as st
import pandas as pd
import pydeck as pdk
import io
import requests
from datetime import datetime, date

st.set_page_config(page_title="Earthquake Map (last month)", layout="wide")
st.title("Earthquake locations — world map")

# ---------- Helpers ----------
def read_csv_from_uploader(uploaded_file):
    try:
        return pd.read_csv(uploaded_file), None
    except Exception as e:
        return None, f"Error reading CSV: {e}"

def fetch_usgs_month():
    url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_month.csv"
    try:
        r = requests.get(url, timeout=12)
        r.raise_for_status()
        return pd.read_csv(io.StringIO(r.text)), None
    except Exception as e:
        return None, f"Error fetching USGS feed: {e}"

def find_first_column(df, candidates):
    lowered = {c.lower(): c for c in df.columns}
import streamlit as st
import pandas as pd
import pydeck as pdk
import io
import requests
from datetime import datetime, date

st.set_page_config(page_title="Earthquake Map (last month)", layout="wide")
st.title("Earthquake locations — world map")

# ---------- Helpers ----------
def read_csv_from_uploader(uploaded_file):
    try:
        return pd.read_csv(uploaded_file), None
    except Exception as e:
        return None, f"Error reading CSV: {e}"

def fetch_usgs_month():
    url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_month.csv"
    try:
        r = requests.get(url, timeout=12)
        r.raise_for_status()
        return pd.read_csv(io.StringIO(r.text)), None
    except Exception as e:
        return None, f"Error fetching USGS feed: {e}"

def find_first_column(df, candidates):
    lowered = {c.lower(): c for c in df.columns}
    for name in candidates:
        if name in lowered:
            return lowered[name]
    return None

def normalize_and_validate(df):
    dfc = df.copy()
    # candidate column names
    lat_col = find_first_column(dfc, ["latitude", "lat", "y"])
    lon_col = find_first_column(dfc, ["longitude", "lon", "lng", "x"])
    mag_col = find_first_column(dfc, ["mag", "magnitude", "m"])
    time_col = find_first_column(dfc, ["time", "datetime", "date", "time_utc"])
    place_col = find_first_column(dfc, ["place", "location", "location_name"])

    if not lat_col or not lon_col:
        return None, "CSV must include latitude and longitude columns (e.g. 'lat','lon' or 'latitude','longitude')."

    rename = {lat_col: "latitude", lon_col: "longitude"}
    if mag_col: rename[mag_col] = "magnitude"
    if time_col: rename[time_col] = "time"
    if place_col: rename[place_col] = "place"
    dfc = dfc.rename(columns=rename)

    # coerce types
    dfc["latitude"] = pd.to_numeric(dfc["latitude"], errors="coerce")
    dfc["longitude"] = pd.to_numeric(dfc["longitude"], errors="coerce")
    if "magnitude" in dfc.columns:
        dfc["magnitude"] = pd.to_numeric(dfc["magnitude"], errors="coerce")
    if "time" in dfc.columns:
        dfc["time"] = pd.to_datetime(dfc["time"], errors="coerce", utc=True)

    # drop invalid lat/lon
    dfc = dfc.dropna(subset=["latitude", "longitude"])
    if dfc.empty:
        return None, "No valid rows after parsing latitude/longitude."

    # enforce ranges
    dfc = dfc[dfc["latitude"].between(-90, 90) & dfc["longitude"].between(-180, 180)]
    if dfc.empty:
        return None, "No events remain after filtering out-of-range coordinates."

    # make time human-readable string for tooltip (if exists)
    if "time" in dfc.columns:
        dfc["time_str"] = dfc["time"].dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    else:
        dfc["time_str"] = ""

    # ensure place column exists for tooltip
    if "place" not in dfc.columns:
        dfc["place"] = ""

    return dfc, None

# ---------- UI: Data source ----------
st.sidebar.header("Data source")
source = st.sidebar.radio("Choose how to load data:", ["Upload CSV", "Fetch USGS (last month)"])

df_raw = None
err = None

if source == "Upload CSV":
    uploaded = st.sidebar.file_uploader("Upload CSV file", type=["csv"])
    if uploaded is not None:
        df_raw, err = read_csv_from_uploader(uploaded)
    else:
        st.info("Upload a CSV or select 'Fetch USGS' to load official feed.")
        st.stop()
else:
    if st.sidebar.button("Fetch USGS now"):
        df_raw, err = fetch_usgs_month()
    else:
        st.sidebar.write("Press the button to fetch the latest monthly feed from USGS.")
        st.stop()

if err:
    st.error(err)
    st.stop()

# ---------- Normalize & validate ----------
df, err = normalize_and_validate(df_raw)
if err:
    st.error(err)
    st.stop()

# ---------- Sidebar summary & filters ----------
st.sidebar.subheader("Summary")
st.sidebar.write(f"Rows loaded: {len(df)}")
if "magnitude" in df.columns:
    st.sidebar.write(f"Magnitude range: {df['magnitude'].min():.2f} — {df['magnitude'].max():.2f}")
if "time" in df.columns:
    st.sidebar.write(f"Date range: {df['time'].dt.date.min()} — {df['time'].dt.date.max()}")

st.sidebar.subheader("Filters")
# magnitude filter
if "magnitude" in df.columns:
    mag_min = float(df["magnitude"].min())
    mag_max = float(df["magnitude"].max())
    mag_range = st.sidebar.slider("Magnitude", mag_min, mag_max, (mag_min, mag_max))
else:
    mag_range = None

# time filter
if "time" in df.columns:
    min_date = df["time"].dt.date.min()
    max_date = df["time"].dt.date.max()
    date_range = st.sidebar.date_input("Date range", [min_date, max_date], min_value=min_date, max_value=max_date)
else:
    date_range = None

# apply filters
df_plot = df.copy()
if mag_range:
    df_plot = df_plot[df_plot["magnitude"].between(mag_range[0], mag_range[1])]
if date_range and len(date_range) == 2:
    start, end = date_range
    df_plot = df_plot[(df_plot["time"].dt.date >= start) & (df_plot["time"].dt.date <= end)]

st.markdown(f"*Showing {len(df_plot)} events after filtering*")

# ---------- Map ----------
if df_plot.empty:
    st.warning("No events to show after applying filters.")
else:
    mid_lat = float(df_plot["latitude"].mean())
    mid_lon = float(df_plot["longitude"].mean())
    view = pdk.ViewState(latitude=mid_lat, longitude=mid_lon, zoom=1.0, pitch=0)

    # choose radius and layer depending on magnitude presence
    if "magnitude" in df_plot.columns:
        layer = pdk.Layer(
            "ScatterplotLayer",
            df_plot,
            pickable=True,
            auto_highlight=True,
            get_position='[longitude, latitude]',
            get_radius="magnitude",
            radius_scale=20000,       # scale magnitude to pixels/meters for visibility
            radius_min_pixels=2,
            radius_max_pixels=200,
            get_fill_color=[255, 140, 0, 160],
        )
    else:
        layer = pdk.Layer(
            "ScatterplotLayer",
            df_plot,
            pickable=True,
            auto_highlight=True,
            get_position='[longitude, latitude]',
            get_radius=10000,
            radius_scale=1,
            get_fill_color=[0, 110, 255, 140],
        )

    tooltip = {
        "html": "<b>Place:</b> {place} <br><b>Mag:</b> {magnitude} <br><b>Time:</b> {time_str}",
        "style": {"backgroundColor": "black", "color": "white"}
    }

    deck = pdk.Deck(layers=[layer], initial_view_state=view, tooltip=tooltip)
    st.pydeck_chart(deck, use_container_width=True)

# ---------- Data table & download ----------
with st.expander("Show data table"):
    st.dataframe(df_plot.reset_index(drop=True))

csv_bytes = df_plot.to_csv(index=False).encode("utf-8")
st.download_button("Download filtered CSV", data=csv_bytes, file_name="earthquakes_filtered.csv", mime="text/csv")