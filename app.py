import io
from pathlib import Path

import numpy as np
import streamlit as st
from PIL import Image, UnidentifiedImageError

from stowaway.pipeline import capacity, receive, send
from stowaway.storm import damage_image, fetch_proton_flux, flux_to_probability

st.set_page_config(page_title="Stowaway", layout="centered")

ROOT = Path(__file__).parent
SPACE_IMAGE = ROOT / "assets" / "space.png"
CHART = ROOT / "assets" / "survival_curve.png"

state = st.session_state
for key in ("original", "stego", "damaged", "flipped", "probability"):
    state.setdefault(key, None)


@st.cache_data(ttl=300, show_spinner="Fetching space-weather data...")
def get_flux():
    return fetch_proton_flux()


def difference_map(a, b):
    """Brightened difference between two images, so a change of 1 shade is visible."""
    diff = np.abs(np.array(a.convert("RGB"), np.int16) - np.array(b.convert("RGB"), np.int16))
    return Image.fromarray(np.clip(diff * 255, 0, 255).astype(np.uint8))


def show_result(column, title, status, text):
    column.markdown(f"**{title}**")
    if status == "ok":
        column.success(text)
    elif status == "damaged":
        column.error("Damaged beyond repair (storm).")
    else:
        column.error("Tampered or wrong password.")


def send_tab():
    st.subheader("Lock and hide a message")
    message = st.text_area("Message")
    password = st.text_input("Password", type="password")
    uploaded = st.file_uploader("Image (PNG only, default is a space image)", type=["png"])

    try:
        image = Image.open(uploaded if uploaded else SPACE_IMAGE).convert("RGB")
    except (UnidentifiedImageError, OSError):
        st.error("That image could not be read. Upload a PNG.")
        return

    used, limit = len(message.encode()), max(capacity(image), 1)
    st.progress(min(used / limit, 1.0), text=f"Capacity used: {used} of {limit} bytes")

    if st.button("Lock and hide", type="primary"):
        if not message or not password:
            st.error("Enter both a message and a password.")
        elif used > limit:
            st.error("Message is too long for this image.")
        else:
            with st.spinner("Locking and hiding..."):
                state.original, state.stego = image, send(image, message, password)
            state.damaged = None
            st.success("Message locked and hidden.")

    if state.stego is not None:
        left, right = st.columns(2)
        left.image(state.original, caption="Original")
        right.image(state.stego, caption="With hidden message")
        st.image(difference_map(state.original, state.stego),
                 caption="Difference map (brightened). Black means nothing changed.")
        buffer = io.BytesIO()
        state.stego.save(buffer, format="PNG")
        st.download_button("Download image (PNG)", buffer.getvalue(), "stowaway.png", "image/png")


def storm_tab():
    st.subheader("Simulate a radiation storm")
    if state.stego is None:
        st.info("Hide a message on the Send tab first.")
        return

    reading = get_flux()
    st.metric("Proton flux (pfu)", f"{reading.flux_pfu:.3g}")
    st.caption(f"Cached data from {reading.observed_at}" if reading.from_cache
               else f"Live NOAA data from {reading.observed_at}")

    boost = st.select_slider("Demo intensity multiplier", [1, 10, 100, 1000, 10000], value=1,
                             help="A quiet day flips almost nothing, so scale the storm up.")
    probability = min(flux_to_probability(reading.flux_pfu) * boost, 0.1)
    st.write(f"Bit-flip probability: **{probability:.2e}**")
    st.caption("This is a model: real flux sets the intensity and we chose the mapping.")

    if st.button("Run storm", type="primary"):
        state.damaged, state.flipped = damage_image(state.stego, probability, seed=42)
        state.probability = probability

    if state.damaged is not None:
        st.image(state.damaged, caption=f"After the storm: {state.flipped:,} bits flipped")


def receive_tab():
    st.subheader("Recover and verify the message")
    if state.damaged is None:
        st.info("Run the storm on the Storm tab first.")
        return

    password = st.text_input("Password", type="password", key="rx_password")
    tamper = st.checkbox("Demonstrate tamper detection (alters the data on purpose)")

    if st.button("Decode", type="primary"):
        if not password:
            st.error("Enter the password.")
            return
        left, right = st.columns(2)
        show_result(left, "With repair data", *receive(state.damaged, password, True, tamper))
        show_result(right, "Without repair data", *receive(state.damaged, password, False))
        st.caption(f"Bits flipped by the storm: {state.flipped:,}")


def results_tab():
    st.subheader("How much storm can the message survive?")
    if CHART.exists():
        st.image(str(CHART), caption="Survival rate vs storm intensity (experiments/survival_curve.py)")
    else:
        st.info("Run experiments/survival_curve.py to generate the chart.")


st.title("Stowaway")
st.caption("Some messages are too important to be lost. Stowaway encrypts a message, hides it in an "
           "image, and recovers it after simulated space radiation damage.")
tabs = st.tabs(["Send", "Storm", "Receive", "Results"])
for tab, screen in zip(tabs, (send_tab, storm_tab, receive_tab, results_tab)):
    with tab:
        screen()