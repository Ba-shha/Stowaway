# Stowaway

> Some messages are too important to be lost. Stowaway encrypts a message, hides it inside an image, and
recovers it after simulated space radiation damage using error correction.

---

## The Problem

While sending information through space two problems are encountered. Signals travel through open space and can be intercepted, and energetic particles from the Sun flip bits in spacecraft electronics (single event upsets).

Stowaway tackles both using encryption, steganography, and Reed–Solomon error
correction. It also measures how severe a simulated radiation storm a hidden
message can survive.

---

## How It Works

1. **Encrypt** — The password is turned into a key using PBKDF2-HMAC-SHA256
   (100,000 iterations, random 16-byte salt). The message is encrypted with
   Fernet, which also provides tamper detection.
2. **Add repair data** — The encrypted bytes are encoded with Reed–Solomon
   (`reedsolo`), using 100 repair bytes per 255-byte block. Each block can
   correct up to 50 corrupted bytes.
3. **Hide** — The result is base64-encoded and written into the least
   significant bits of the image pixels. Each pixel changes by at most 1 shade
   out of 255, so the image looks unchanged.
4. **Simulate the storm** — The app fetches live ≥10 MeV proton flux from NOAA
   SWPC (GOES satellite data) and maps it to a bit-flip probability on a log
   scale. Random bits of the image are then flipped.
5. **Recover** — Extraction runs in two steps so failure modes stay distinct:

   | Result | Meaning |
   |---|---|
   | Message shown | Repair and decryption both succeeded |
   | "Recovery failed: corrupted beyond what the repair data can correct" | Too many errors from the storm |
   | "Integrity check failed: altered data or wrong password" | Repair worked, but decryption was refused |

---

## The App

The Streamlit app has three tabs:

- **Prepare** — Enter a message and password, choose a PNG (or use the bundled
  space image), and see a capacity bar. Output is the stego image plus a
  difference map. Download it as PNG.
- **Transmit** — Upload an image, enter the password, and optionally simulate a
  radiation storm. Results are shown side by side with and without repair data.
  A "Simulate an attacker" option alters one byte to demonstrate tamper detection.
- **Survival** — Runs the survival experiment live, or shows the saved chart.

Storm severity levels scale the bit-flip probability from the live NOAA reading
(×1, ×100, ×1,000, ×10,000, capped at 10%). Real conditions are usually too
mild to damage the image, so higher levels exist for demonstration.

---

## Results

The experiment in `experiments/survival_curve.py` runs the full pipeline
(encrypt → repair → hide → storm → recover) on a 300×300 crop of the space
image, with 100 trials per storm level and fixed seeds so reruns match.

Raw numbers: `results/survival_curve.csv`
Chart: `assets/survival_curve.png`

| Bit-flip chance | Recovered (with repair) | Recovered (without repair) |
|---|---|---|
| 0%    | 100% | 100% |
| 0.1%  | 97%  | 19%  |
| 0.2%  | 99%  | 1%   |
| 0.3%  | 91%  | 0%   |
| 0.5%  | 95%  | 0%   |
| 0.7%  | 73%  | 0%   |
| 1%    | 72%  | 0%   |
| 1.5%  | 50%  | 0%   |
| 2%    | 10%  | 0%   |
| 3%    | 0%   | 0%   |

Without repair data, the message almost never survives once bits start
flipping. With repair data, most messages survive up to about 1% bit-flip
probability, then survival falls off steeply between 1.5% and 3%. Small
variations at low intensities (97% at 0.1% vs 99% at 0.2%) are expected from
100 random trials per level.

---

## How to Run

Requires Python 3.10 or newer.

```bash
git clone https://github.com/Ba-shha/Stowaway.git
cd Stowaway
pip install -r requirements.txt
```

```bash
streamlit run app.py                  # launch the app
python -m experiments.survival_curve  # regenerate chart and CSV
pytest                                # run the tests
```

---

## Project Structure

```
Stowaway/
├── app.py                    # Streamlit interface (Encode, Decode, Survival)
├── stowaway/
│   ├── crypto.py             # password → key, lock / unlock (Fernet)
│   ├── repair.py             # Reed–Solomon protect / repair
│   ├── hide.py               # hide / reveal text in image LSBs
│   ├── storm.py              # NOAA fetch, cache, flux → probability, damage
│   └── pipeline.py           # connects the stages: send / receive
├── experiments/
│   └── survival_curve.py     # survival experiment and chart
├── tests/                    # roundtrip, wrong password, tamper, repair, storm cache
├── assets/                   # space image and chart
├── data/noaa_cache.json      # last good NOAA reading (offline fallback)
└── results/survival_curve.csv
```

---

## Limitations

- **The storm is a model.** Real proton flux sets the intensity, but the mapping
  from flux to bit-flip probability is our own choice, not a radiation-physics
  simulation.
- **LSB hiding breaks under JPEG, resizing, or messaging apps.** The image must
  stay a lossless PNG.
- **LSB is easy to detect** with steganalysis tools. Security comes from the
  encryption, not the hiding.
- **The length header is not separately protected.** If a storm damages it,
  recovery fails even if the rest of the data is repairable.
- **Storms and attackers are not always distinguishable.** An attacker who flips
  only a few bits will be silently repaired, exactly like a storm.
- **Capacity is limited** by image size and repair strength.

### Future Work

- Frequency-domain hiding that survives compression
- A more physical radiation model
- Password-seeded scattering of bit positions
- Comparing several repair strengths
- Stronger schemes for burst errors

---

## Theme Connection

Cosmo Polo carries knowledge across worlds. Stowaway is the traveller's hidden
cargo: a message that crosses a watched, radiation-filled sky and arrives intact.

---

## Credits

- Space weather data: [NOAA Space Weather Prediction Center](https://www.swpc.noaa.gov/) (GOES proton flux)
- Libraries: [Streamlit](https://streamlit.io/), [Pillow](https://python-pillow.org/), [NumPy](https://numpy.org/), [cryptography](https://cryptography.io/), [reedsolo](https://github.com/tomerfiliba-org/reedsolomon), [stegano](https://github.com/cedricbonhomme/Stegano), [requests](https://requests.readthedocs.io/), [Matplotlib](https://matplotlib.org/), [pytest](https://pytest.org/)

---

## License

MIT. See [LICENSE](LICENSE).
