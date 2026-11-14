
import streamlit as st

st.set_page_config(
    page_title="Hawk Lens",
    layout="wide"
)

st.title("Hawk Lens")
st.subheader("Building 3 — Houston, Texas")

st.write("Commercial Building Energy & Retrofit Analysis")

tab1, tab2 = st.tabs([
    "Aerial View",
    "3D Building Tour"
])

with tab1:
    st.image(
        "vexcel/houston_building.jpg",
        caption="Vexcel Aerial Imagery",
        use_column_width=True
    )

with tab2:
    matterport_url = (
        "https://my.matterport.com/show/?m=9yBnBD3ievg"
    )

    st.components.v1.iframe(
        matterport_url,
        height=650,
        scrolling=True
    )

st.divider()

st.subheader("Building Information")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Floors", "1")

with col2:
    st.metric("Rooms", "2")

with col3:
    st.metric("3D Panoramas", "15")

st.caption("Data sources: Vexcel and Matterport")
