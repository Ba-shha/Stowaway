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

# Storm levels scale the bit-flip probability derived from the live NOAA reading.
STORMS = {"Observed conditions": 1, "Moderate": 100, "Severe": 1_000, "Extreme": 10_000}
ERRORS = {
    "damaged": "Recovery failed: the image is corrupted beyond what the repair data can correct.",
    "tampered": "Integrity check failed: the data was altered, or the password is wrong. No message shown.",
}

state = st.session_state
state.setdefault("stego", None)


@st.cache_data(ttl=300, show_spinner="Retrieving space-weather data...")
def get_flux():
    return fetch_proton_flux()


def load(source):
    try:
        return Image.open(source).convert("RGB")
    except (UnidentifiedImageError, OSError):
        st.error("The image could not be read. Use a PNG file.")


def png(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def encode_tab():
    st.header("Encode message")
    st.info("Enter a message and a password, then press **Encode**. The message is encrypted, given "
            "repair data and hidden in the image. Save the resulting image: it carries the message.")
    uploaded = st.file_uploader("Image (PNG). Leave empty to use the bundled space telescope image.",
                                type=["png"])
    message = st.text_area("Message", placeholder="Enter your message here")
    password = st.text_input("Password", type="password")

    image = load(uploaded or SPACE_IMAGE)
    if image is None:
        return
    used, limit = len(message.encode()), max(capacity(image), 1)
    st.progress(min(used / limit, 1.0), text=f"Capacity used: {used:,} of {limit:,} bytes")

    if st.button("Encode"):
        if not message or not password:
            st.error("Enter both a message and a password.")
        elif used > limit:
            st.error("The message is too long for this image.")
        else:
            state.original, state.stego = image, send(image, message, password)

    if state.stego is not None:
        st.success("Message encoded. Save the image below, or go to the Decode tab.")
        left, right = st.columns(2)
        left.image(state.original, caption="Original")
        right.image(state.stego, caption="With hidden message")
        diff = np.abs(np.array(state.original, np.int16) - np.array(state.stego, np.int16))
        with st.expander("Difference map"):
            st.image(Image.fromarray(np.clip(diff * 255, 0, 255).astype(np.uint8)),
                     caption="Changed pixels, brightened. Each differs by one shade out of 255.")
        st.download_button("Save image (PNG)", png(state.stego), "stowaway.png", "image/png")


def decode_tab():
    st.header("Decode message")
    st.info("Choose the image that carries the message and enter the password. Optionally expose it to a "
            "simulated radiation storm first, to test whether the message survives the journey. "
            "Results are shown with and without repair data.")
    uploaded = st.file_uploader("Image (PNG). Leave empty to use the image from the Encode tab.",
                                type=["png"], key="decode_image")
    image = load(uploaded) if uploaded else state.stego
    if image is None:
        st.warning("Encode a message first, or upload an encoded PNG.")
        return
    password = st.text_input("Password", type="password", key="decode_password")

    storm = st.checkbox("Simulate a radiation storm in transit")
    flipped = None
    if storm:
        try:
            reading = get_flux()
        except RuntimeError:
            st.error("NOAA is unreachable and no saved reading exists.")
            return
        level = st.select_slider("Storm severity", list(STORMS),
                                 help="Observed conditions are usually too mild to damage the image, "
                                      "so higher levels scale the reading up for demonstration.")
        probability = min(flux_to_probability(reading.flux_pfu) * STORMS[level], 0.1)
        source = "saved reading" if reading.from_cache else "live NOAA GOES data"
        st.caption(f"Proton flux {reading.flux_pfu:.3g} pfu ({source}, {reading.observed_at}). "
                   f"Bit-flip probability {probability:.2e}. This is a model: the flux sets the "
                   "intensity and the mapping to bit flips is our own.")
    attack = st.checkbox("Simulate an attacker", help="Alters the recovered data to demonstrate tamper detection.")

    if st.button("Decode"):
        if not password:
            st.error("Enter the password.")
            return
        if storm:
            image, flipped = damage_image(image, probability, seed=42)
            with st.expander(f"Image after the storm ({flipped:,} bits flipped)"):
                st.image(image)
        for column, title, use_repair in zip(st.columns(2), ("With repair data", "Without repair data"),
                                             (True, False)):
            status, text = receive(image, password, use_repair, attack and use_repair)
            column.markdown(f"**{title}**")
            column.success(text) if status == "ok" else column.error(ERRORS[status])


def survival_tab():
    st.header("Survival")
    st.info("How much corruption can a hidden message withstand? Each storm level damages a small test "
            "image repeatedly and counts how often the message is recovered, using the same code as the app.")
    trials = st.slider("Trials per storm level", 5, 100, 20)
    if st.button("Run experiment"):
        probs, with_repair, without_repair = [], [], []
        bar, chart = st.progress(0.0), st.empty()
        for done, (p, a, b) in enumerate(run_levels(trials), start=1):
            probs.append(p), with_repair.append(a), without_repair.append(b)
            chart.pyplot(make_chart(probs, with_repair, without_repair, trials))
            bar.progress(done / len(LEVELS))
    elif CHART.exists():
        st.image(str(CHART), caption="Saved result from experiments/survival_curve.py")


st.title("Stowaway")
st.caption("Encrypted, hidden and error-corrected messaging for channels that are watched and noisy.")
for tab, screen in zip(st.tabs(["Encode", "Decode", "Survival"]), (encode_tab, decode_tab, survival_tab)):
    with tab:
        screen()