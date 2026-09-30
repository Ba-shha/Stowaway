import html
import io
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image, UnidentifiedImageError

from experiments.survival_curve import LEVELS, run_levels
from stowaway.pipeline import capacity, receive, send
from stowaway.storm import damage_image, fetch_proton_flux, flux_to_probability

st.set_page_config(page_title="Stowaway", layout="centered")

ROOT = Path(__file__).parent
SPACE_IMAGE = ROOT / "assets" / "space.png"
RESULTS = ROOT / "results" / "survival_curve.csv"

# Storm levels scale the bit-flip probability derived from the live NOAA reading.
STORMS = {"Observed conditions": 1, "Moderate": 100, "Severe": 1_000, "Extreme": 10_000}
LOST = {True: "Message lost. The storm corrupted more than the repair data can correct.",
        False: "Message lost. Without repair data, the storm damage cannot be corrected."}
ALARM = "Tamper alarm. The data was altered in transit, or the password is wrong. No message is shown."

st.markdown("""
<style>
html {font-size: 18px;}
html, body, .stApp {font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;}
.block-container {max-width: 1040px; padding-top: 2.5rem;}
h1 {font-size: 2.1rem !important; font-weight: 600 !important; padding-bottom: 0.2rem;}
h2, h3 {font-size: 1.35rem !important; font-weight: 600 !important;}
p, label, li {font-size: 1rem;}
[data-testid="stCaptionContainer"] {font-size: 0.9rem;}
[data-baseweb="textarea"], [data-baseweb="input"], [data-baseweb="select"] > div {
    background: transparent !important; border: 1px solid rgba(128,128,128,.4) !important;
    border-radius: 6px !important;}
[data-baseweb="textarea"] textarea, [data-baseweb="input"] input {background: transparent !important;}
[data-baseweb="textarea"]:focus-within, [data-baseweb="input"]:focus-within {
    border-color: #0969da !important; box-shadow: 0 0 0 3px rgba(9,105,218,.15);}
[data-testid="stFileUploaderDropzone"] {
    background: transparent; border: 1px dashed rgba(128,128,128,.5); border-radius: 6px; padding: .5rem .8rem;}
[data-testid="stFileUploaderDropzoneInstructions"] {display: none;}
button[kind="primary"], button[data-testid="stBaseButton-primary"] {
    background: #0969da; border: 1px solid #0969da; border-radius: 6px; font-weight: 500;}
button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover {background: #0550ae; border-color: #0550ae;}
button[kind="secondary"], button[data-testid="stBaseButton-secondary"] {border-radius: 6px;}
.lbl {display: flex; align-items: center; gap: .45rem; font-size: 1rem; margin: .6rem 0 .25rem;}
.tip {position: relative; display: inline-flex; align-items: center; justify-content: center; width: 1.05rem;
    height: 1.05rem; border: 1.5px solid rgba(128,128,128,.8); border-radius: 50%; font-size: .68rem;
    font-weight: 600; color: rgba(128,128,128,.95); cursor: help;}
.tip:hover::after {content: attr(data-tip); position: absolute; left: -.5rem; top: 1.6rem; width: 300px;
    padding: .55rem .7rem; background: #1f2328; color: #fff; border-radius: 6px; font-size: .85rem;
    font-weight: 400; line-height: 1.4; z-index: 1000; box-shadow: 0 4px 14px rgba(0,0,0,.3);}
</style>
""", unsafe_allow_html=True)


def label(text, tip=""):
    """A field label with its help icon right beside it."""
    icon = f'<span class="tip" data-tip="{html.escape(tip, quote=True)}">?</span>' if tip else ""
    st.markdown(f'<div class="lbl">{text}{icon}</div>', unsafe_allow_html=True)


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


def prepare_tab():
    st.subheader("Prepare the message")
    st.caption("Encrypt a message and hide it in an image.")
    label("Message", "Encrypted with your password before it is hidden in the image.")
    message = st.text_area("Message", placeholder="Type the message to protect", height=120,
                           label_visibility="collapsed")
    label("Password", "Creates the encryption key. The receiver needs the same password.")
    password = st.text_input("Password", type="password", label_visibility="collapsed")
    with st.expander("Use your own image (optional)"):
        st.caption("PNG only. By default the bundled space telescope image is used.")
        uploaded = st.file_uploader("Image", type=["png"], label_visibility="collapsed")

    image = load(uploaded or SPACE_IMAGE)
    if image is None:
        return
    used, limit = len(message.encode()), max(capacity(image), 1)
    st.progress(min(used / limit, 1.0), text=f"{used:,} of {limit:,} bytes used")

    if st.button("Encode message", type="primary"):
        if not message or not password:
            st.error("Enter both a message and a password.")
        elif used > limit:
            st.error("The message is too long for this image.")
        else:
            state.original, state.stego = image, send(image, message, password)

    if state.stego is not None:
        st.success("Message encoded. Continue to Transmit.")
        left, right = st.columns(2)
        left.image(state.original, caption="Original")
        right.image(state.stego, caption="Carrying the message")
        diff = np.abs(np.array(state.original, np.int16) - np.array(state.stego, np.int16))
        with st.expander("What changed?"):
            st.image(Image.fromarray(np.clip(diff * 255, 0, 255).astype(np.uint8)),
                     caption="Changed pixels, brightened. Each differs by one shade out of 255, "
                             "so the two images look identical.")
        st.download_button("Save image (PNG)", png(state.stego), "stowaway.png", "image/png")


def transmit_tab():
    st.subheader("Transmit through a solar storm")
    st.caption("Send the image through simulated cosmic radiation and try to recover the message.")
    with st.expander("Use a different image (optional)"):
        st.caption("Upload an encoded PNG. By default the image from the Prepare tab is used.")
        uploaded = st.file_uploader("Image", type=["png"], key="transmit_image", label_visibility="collapsed")
    image = load(uploaded) if uploaded else state.stego
    if image is None:
        st.warning("Prepare a message first, or upload an encoded PNG.")
        return
    try:
        reading = get_flux()
    except RuntimeError:
        st.error("NOAA is unreachable and no saved reading exists.")
        return

    label("Storm severity", "Energetic solar protons flip bits in space electronics. The current NOAA GOES "
                            "proton flux sets the intensity scale. Observed conditions rarely damage the "
                            "image, so higher levels scale it up for demonstration. This is a model, "
                            "not a physics simulation.")
    level = st.select_slider("Storm severity", list(STORMS), label_visibility="collapsed")
    probability = min(flux_to_probability(reading.flux_pfu) * STORMS[level], 0.1)
    source = "Saved NOAA reading" if reading.from_cache else "Live NOAA GOES data"
    st.caption(f"{source}: {reading.flux_pfu:.3g} pfu, observed {reading.observed_at}. "
               f"Bit-flip probability {probability:.2e} per bit.")

    left, right = st.columns(2)
    repair_on = left.toggle("Repair data", value=True,
                            help="Reed-Solomon error correction added before hiding. Turn it off and "
                                 "transmit again to see the same storm destroy the message.")
    attack = right.checkbox("Interceptor alters the data",
                            help="Demonstrates tamper detection: altered data is rejected, never shown as text.")
    label("Receiver's password")
    password = st.text_input("Receiver's password", type="password", key="receiver_password",
                             label_visibility="collapsed")

    if st.button("Transmit", type="primary"):
        if not password:
            st.error("Enter the password.")
            return
        damaged, flipped = damage_image(image, probability, seed=42)
        status, text = receive(damaged, password, repair_on, attack and repair_on)
        st.image(damaged, caption=f"As received: {flipped:,} bits flipped in transit")
        if status == "ok":
            st.success(f"Message received: {text}")
        else:
            st.error(ALARM if status == "tampered" else LOST[repair_on])


def curve(rows):
    """Rows of (bit-flip probability, % with repair, % without) as a chart-ready table."""
    table = pd.DataFrame(rows, columns=["flip", "With repair data", "Without repair data"])
    table["flip"] *= 100
    return table.set_index("flip")


def show_curve(container, table):
    container.line_chart(table, height=320)
    container.caption("Across: how much of the image the storm corrupted (% of bits flipped). "
                      "Up: how many messages were recovered intact (%).")


def evidence_tab():
    st.subheader("Evidence")
    st.caption("How much radiation damage can a hidden message survive, and what does repair data add?")
    if RESULTS.exists():
        saved = pd.read_csv(RESULTS)
        runs = int(saved["trials"].iloc[0])
        row = saved.iloc[(saved["flip_probability"] - 0.01).abs().argmin()]
        st.markdown(f"When **1 in 100 bits** in the image is flipped, **{row.with_repair_pct:.0f}%** of "
                    f"messages are recovered with repair data, against **{row.without_repair_pct:.0f}%** without it.")
        show_curve(st, curve(saved.iloc[:, :3].to_numpy()))
        st.caption(f"Measured by our own experiment: {runs} test runs at each storm strength, "
                   "using the same encoding and recovery as this app.")

    with st.expander("Run the experiment yourself"):
        label("Test runs per storm strength", "A test image is damaged this many times at each strength, "
                                              "and we count how often the message comes back. More runs "
                                              "give a smoother line but take longer.")
        trials = st.slider("Test runs per storm strength", 5, 100, 20, label_visibility="collapsed")
        if st.button("Run experiment", type="primary"):
            rows, bar, chart = [], st.progress(0.0), st.empty()
            for done, row in enumerate(run_levels(trials), start=1):
                rows.append(row)
                show_curve(chart.container(), curve(rows))
                bar.progress(done / len(LEVELS))


st.title("Stowaway")
st.caption("Stowaway hides an encrypted message inside a space telescope image, then tests whether it "
           "survives a simulated solar radiation storm.")
for tab, screen in zip(st.tabs(["1. Prepare", "2. Transmit", "3. Evidence"]),
                        (prepare_tab, transmit_tab, evidence_tab)):
    with tab:
        screen()