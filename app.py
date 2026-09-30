import io
from pathlib import Path

import numpy as np
import streamlit as st
from PIL import Image, UnidentifiedImageError

from experiments.survival_curve import LEVELS, make_chart, run_levels
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


def png_bytes(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def pick_image(label, key, fallback, fallback_note):
    """An uploaded PNG wins. Otherwise use the image from the previous tab, if there is one."""
    uploaded = st.file_uploader(label, type=["png"], key=key)
    if uploaded:
        try:
            return Image.open(uploaded).convert("RGB")
        except (UnidentifiedImageError, OSError):
            st.error("That file could not be read. Upload a PNG.")
            return None
    if fallback is not None:
        st.caption(fallback_note)
        return fallback
    st.info("Upload a PNG above, or create one on the earlier tabs.")
    return None


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
        st.download_button("Download image (PNG)", png_bytes(state.stego), "stowaway.png", "image/png")
        st.caption("Send this file to anyone. They decode it on the Receive tab with the password. "
                   "Keep it as a PNG: JPEG, resizing or WhatsApp destroy the hidden message.")


def storm_tab():
    st.subheader("Simulate a radiation storm")
    image = pick_image("Image to damage (upload the PNG from Send, or skip to use it directly)",
                       "storm_upload", state.stego, "Using the image from the Send tab.")
    if image is None:
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
        state.damaged, state.flipped = damage_image(image, probability, seed=42)
        state.probability = probability

    if state.damaged is not None:
        st.image(state.damaged, caption=f"After the storm: {state.flipped:,} bits flipped")
        st.download_button("Download damaged image (PNG)", png_bytes(state.damaged),
                           "stowaway_damaged.png", "image/png")


def receive_tab():
    st.subheader("Recover and verify the message")
    image = pick_image("Image to decode (upload a PNG, or skip to use the storm-damaged one)",
                       "rx_upload", state.damaged, "Using the damaged image from the Storm tab.")
    if image is None:
        return

    password = st.text_input("Password", type="password", key="rx_password")
    tamper = st.checkbox("Demonstrate tamper detection (alters the data on purpose)")

    if st.button("Decode", type="primary"):
        if not password:
            st.error("Enter the password.")
            return
        left, right = st.columns(2)
        show_result(left, "With repair data", *receive(image, password, True, tamper))
        show_result(right, "Without repair data", *receive(image, password, False))
        if state.flipped is not None and image is state.damaged:
            st.caption(f"Bits flipped by the storm: {state.flipped:,}")


def results_tab():
    st.subheader("How much storm can the message survive?")
    st.caption("Each storm level damages a small test image many times and counts how often the "
               "message comes back. Same code path as the app: lock, repair data, hide, storm, decode.")
    trials = st.slider("Trials per storm level", 5, 100, 20,
                       help="More trials give a smoother curve but take longer.")

    if st.button("Run live experiment", type="primary"):
        probs, with_repair, without_repair = [], [], []
        bar = st.progress(0.0, text="Starting...")
        chart = st.empty()
        for done, (p, a, b) in enumerate(run_levels(trials), start=1):
            probs.append(p)
            with_repair.append(a)
            without_repair.append(b)
            chart.pyplot(make_chart(probs, with_repair, without_repair, trials))
            bar.progress(done / len(LEVELS), text=f"Storm level {done} of {len(LEVELS)} done")
        bar.empty()
        st.caption(f"Live run with {trials} trials per level. The official 100-trial chart comes "
                   "from `python -m experiments.survival_curve`.")
    elif CHART.exists():
        st.image(str(CHART), caption="Saved result from experiments/survival_curve.py. "
                                     "Press the button to draw it live.")


st.title("Stowaway")
st.caption("Some messages are too important to be lost. Stowaway encrypts a message, hides it in an "
           "image, and recovers it after simulated space radiation damage.")
tabs = st.tabs(["Send", "Storm", "Receive", "Results"])
for tab, screen in zip(tabs, (send_tab, storm_tab, receive_tab, results_tab)):
    with tab:
        screen()