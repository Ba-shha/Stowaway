import io
from pathlib import Path

import numpy as np
import streamlit as st
from PIL import Image, UnidentifiedImageError

# ---------------------------------------------------------------
# Page setup (must be the first Streamlit command)
# ---------------------------------------------------------------
st.set_page_config(
    page_title="Stowaway",
    layout="centered",
    initial_sidebar_state="collapsed",
)

DEMO_MODE = True  # set to False once every stand-in is replaced

# Paths are built from this file's location, so the app works no matter
# which folder you launch it from.
BASE_DIR = Path(__file__).parent
DEFAULT_IMAGE_PATH = BASE_DIR / "assets" / "space.png"  # NASA Webb/Hubble PNG
CHART_PATH = BASE_DIR / "assets" / "survival_curve.png"


# ---------------------------------------------------------------
# BACKEND: temporary stand-ins. Replace these with the real modules.
# ---------------------------------------------------------------

def hide_message(image, message, password):
    """STAND-IN. Real version: lock (crypto.py) + repair (repair.py) + hide (hide.py),
    chained by pipeline.py. Should return the stego image (a PIL image)."""
    return image.copy()


def get_flux():
    """STAND-IN. Real version: storm.py fetches NOAA proton flux, with cache fallback.
    Should return (flux_value, label_text)."""
    return 1250.0, "Demo value (not live NOAA data)"


def flux_to_probability(flux):
    """STAND-IN. Real version: storm.py maps flux to bit-flip probability (log scale)."""
    return min(0.05, flux * 1e-5)


def damage_image(image, probability, seed=0):
    """STAND-IN. Real version: storm.py flips random bits in the image.
    Returns (damaged_image, number_of_bits_flipped)."""
    rng = np.random.default_rng(seed)
    pixels = np.array(image.convert("RGB"), dtype=np.uint8)
    flip_mask = rng.random(pixels.shape) < probability  # which values get hit
    pixels[flip_mask] ^= 1                              # flip the lowest bit
    return Image.fromarray(pixels), int(flip_mask.sum())


def receive_message(image, password, use_repair):
    """STAND-IN. Real version: extract (hide.py), repair (repair.py), unlock (crypto.py).
    Should return (status, text) where status is one of:
    'ok', 'damaged', 'tampered'."""
    return "damaged", ""


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

def difference_map(original, changed):
    """Shows where two images differ, brightened so tiny changes are visible."""
    a = np.array(original.convert("RGB"), dtype=np.int16)
    b = np.array(changed.convert("RGB"), dtype=np.int16)
    diff = np.abs(a - b) * 255  # brighten: a difference of 1 becomes fully bright
    return Image.fromarray(np.clip(diff, 0, 255).astype(np.uint8))


@st.cache_resource(show_spinner=False)
def load_default_image():
    """Load the bundled space image (or make a plain starfield if it is missing).
    Cached: the file is read once, not on every button click."""
    if DEFAULT_IMAGE_PATH.exists():
        return Image.open(DEFAULT_IMAGE_PATH).convert("RGB")
    rng = np.random.default_rng(1)
    stars = (rng.random((400, 600, 3)) > 0.995) * 255
    return Image.fromarray(stars.astype(np.uint8))


@st.cache_data(ttl=300, show_spinner="Fetching space-weather data...")
def cached_flux():
    """Ask for the flux at most once every 5 minutes, so the real NOAA server
    is not called on every click."""
    return get_flux()


def load_chosen_image(uploaded):
    """Return the uploaded PNG, or the default image. Returns None if the upload is unreadable."""
    if uploaded is None:
        return load_default_image()
    try:
        return Image.open(uploaded).convert("RGB")
    except (UnidentifiedImageError, OSError):
        st.error("That file could not be read as an image. Please upload a valid PNG.")
        return None


def capacity_bytes(image):
    """Rough capacity: 1 hidden bit per colour value, minus a safety margin.
    TODO: replace with the real capacity check from hide.py (it should also
    account for encryption overhead and repair bytes)."""
    width, height = image.size
    return (width * height * 3) // 8 // 4


# session_state is Streamlit's memory: it keeps values when you switch tabs.
# (The password is deliberately NOT stored here.)
state = st.session_state
for key, default in {
    "original": None, "stego": None, "damaged": None, "diff_map": None,
    "message": "", "probability": None, "flipped": 0,
}.items():
    state.setdefault(key, default)


# ---------------------------------------------------------------
# Tab 1: Send
# ---------------------------------------------------------------

def screen_send():
    st.subheader("Lock and hide a message")
    st.caption("Enter a message and a password. The message is encrypted, then hidden "
               "inside the image. Only lossless PNG images work.")

    message = st.text_area("Message", value=state.message, placeholder="Enter your message here")
    password = st.text_input("Password", type="password")
    uploaded = st.file_uploader("Image (optional, PNG only)", type=["png"])

    image = load_chosen_image(uploaded)
    if image is None:
        return

    used = len(message.encode("utf-8"))
    limit = max(capacity_bytes(image), 1)  # never divide by zero
    st.progress(min(used / limit, 1.0), text=f"Capacity used: {used} of about {limit} bytes")

    if st.button("Lock and hide", type="primary"):
        if not message or not password:
            st.error("Please enter both a message and a password.")
        elif used > limit:
            st.error("Message is too long for this image. Use a shorter message or a bigger image.")
        else:
            with st.spinner("Locking and hiding..."):
                state.original = image
                state.stego = hide_message(image, message, password)
                state.diff_map = difference_map(image, state.stego)  # computed once, reused
            state.message = message
            state.damaged = None
            st.success("Message locked and hidden.")

    if state.stego is not None:
        left, right = st.columns(2)
        left.image(state.original, caption="Original")
        right.image(state.stego, caption="With hidden message")
        st.image(state.diff_map,
                 caption="Difference map (brightened). Black means nothing changed.")

        # Always save as lossless PNG: JPEG, resizing or screenshots would destroy the message.
        buffer = io.BytesIO()
        state.stego.save(buffer, format="PNG")
        st.download_button("Download image (PNG)", buffer.getvalue(),
                           file_name="stowaway.png", mime="image/png")


# ---------------------------------------------------------------
# Tab 2: Storm
# ---------------------------------------------------------------

def screen_storm():
    st.subheader("Simulate a radiation storm")
    st.caption("Current space-weather data sets how many bits in the image get flipped.")

    if state.stego is None:
        st.info("Hide a message on the Send tab first.")
        return

    flux, label = cached_flux()
    probability = flux_to_probability(flux)
    st.metric("Proton flux", f"{flux:g}")
    st.caption(label)
    if st.button("Refresh space-weather data"):
        cached_flux.clear()
        st.rerun()

    st.write(f"Bit-flip probability from this flux: **{probability:.6f}**")
    st.caption("This is a model: real flux sets the intensity, we chose the mapping.")

    if st.button("Run storm", type="primary"):
        with st.spinner("Storm in progress..."):
            state.damaged, state.flipped = damage_image(state.stego, probability)
        state.probability = probability

    if state.damaged is not None:
        st.image(state.damaged, caption=f"After storm: {state.flipped} values flipped")


# ---------------------------------------------------------------
# Tab 3: Receive
# ---------------------------------------------------------------

def screen_receive():
    st.subheader("Recover and verify the message")
    st.caption("Decode the damaged image. Repair data corrects storm damage; "
               "encryption detects tampering.")

    if state.damaged is None:
        st.info("Run the storm on the Storm tab first.")
        return

    password = st.text_input("Password", type="password", key="rx_password")
    use_repair = st.toggle("Use repair data", value=True)

    if st.button("Decode", type="primary"):
        if not password:
            st.error("Please enter the password.")
        else:
            status, text = receive_message(state.damaged, password, use_repair)
            if status == "ok":
                st.success("Message recovered:")
                st.code(text, language=None)  # shows the text exactly as it is
            elif status == "damaged":
                st.error("Damaged beyond repair (storm).")
            elif status == "tampered":
                st.error("Tampered or wrong password.")
            else:
                st.warning(f"Unexpected result from the decoder: {status!r}")

    st.caption(f"Bits flipped by the storm: {state.flipped}")
    # TODO: add the "Demonstrate tamper detection" button once the real pipeline exists.


# ---------------------------------------------------------------
# Tab 4: Results
# ---------------------------------------------------------------

def screen_results():
    st.subheader("How much storm can the message survive?")
    if CHART_PATH.exists():
        st.image(str(CHART_PATH),
                 caption="Survival rate vs storm intensity (from experiments/survival_curve.py)")
    else:
        st.info("The survival curve appears here after experiments/survival_curve.py is run.")


# ---------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------
st.title("Stowaway")
st.caption("Some messages are too important to be lost. Stowaway is a steganography tool that encrypts a message, hides it in an image, and recovers it after simulated space radiation damage using error correction.")
if DEMO_MODE:
    st.caption("Try it!")

tab_send, tab_storm, tab_receive, tab_results = st.tabs(["Send", "Storm", "Receive", "Results"])
with tab_send:
    screen_send()
with tab_storm:
    screen_storm()
with tab_receive:
    screen_receive()
with tab_results:
    screen_results()