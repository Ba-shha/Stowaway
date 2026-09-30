# Stowaway

> Some messages are too important to be lost. Stowaway encrypts a message, hides it in a space telescope image, and recovers it after simulated space radiation damage using error correction.

\<!-- TODO: add a screenshot or GIF of the app here, e.g. !\[Stowaway]\(assets/screenshot.png) -->

`Lock -> Repair data -> Hide -> Survive -> Verify`

## The problem

While sending information through space two problems are encountered. Signals travel through open space and can be intercepted, and energetic particles from the Sun flip bits in spacecraft electronics (_single event upsets_). This is where Stowaway, using techniques like Reed-Solomon, Steganography and Encryption to send information securely. It also **measures** how much simulated storm a hidden message can survive.

## How it works

1. **Lock (encryption).** Your password is turned into a key with PBKDF2-HMAC-SHA256 (100,000 iterations) and a random 16-byte salt. The message is encrypted with Fernet, which provides encryption and tamper detection. Without the password the message is gibberish, and if a single byte is altered, decryption refuses.
2. **Add repair data (Reed-Solomon).** The locked bytes are encoded with `reedsolo`, using 100 repair bytes per 255-byte block. Each block can correct up to 50 corrupted bytes.
3. **Hide (steganography).** The result is base64-encoded and written into the least significant bits of the image's pixels using the `stegano` library. Each pixel changes by at most 1 shade out of 255, so the image looks unchanged.
4. **Survive the storm (simulation).** The app fetches the current >=10 MeV proton flux from NOAA SWPC (GOES satellite data) and maps it to a bit-flip probability on a log scale. Random bits of the image are then flipped. If NOAA is unreachable, the app falls back to the last cached reading (`data/noaa_cache.json`) and labels it as saved.
5. **Verify (receive).** Extraction runs in two separate steps, so the app can tell the failure modes apart:

| Result                                                               | Meaning                                   |
| -------------------------------------------------------------------- | ----------------------------------------- |
| Message shown                                                        | Repair and decryption both succeeded      |
| "Recovery failed: corrupted beyond what the repair data can correct" | Too many errors from the storm            |
| "Integrity check failed: altered data or wrong password"             | Repair worked, but decryption was refused |

## The app

Run it and you get three tabs:

* **Encode:** enter a message and password, choose a PNG (or use the bundled space image), and see a capacity bar. The output is the stego image plus a difference map showing what changed. Download it as a PNG.
* **Decode:** upload the image (or use the one from Encode), enter the password, and optionally simulate a radiation storm. Results are shown side by side **with** and **without** repair data. A "Simulate an attacker" option alters one byte of the recovered data to demonstrate tamper detection.
* **Survival:** runs the survival experiment live, or shows the saved chart.

Storm severity levels scale the bit-flip probability derived from the live NOAA reading (x1, x100, x1,000 and x10,000, capped at 10%). Observed conditions are usually too mild to damage the image, so the higher levels exist for demonstration.

## Results

The experiment in `experiments/survival_curve.py` runs the real pipeline (lock, repair data, hide, storm, receive) on a 300x300 crop of the space image, with 100 trials per storm level and fixed seeds so reruns match. Raw numbers are in `results/survival_curve.csv`, and the chart is saved to `assets/survival_curve.png`.

![Survival rate vs storm intensity](https://claude.ai/chat/assets/survival_curve.png)

| Chance each bit flips | Recovered with repair data | Recovered without repair data |
| --------------------- | -------------------------- | ----------------------------- |
| 0%                    | 100%                       | 100%                          |
| 0.1%                  | 97%                        | 19%                           |
| 0.2%                  | 99%                        | 1%                            |
| 0.3%                  | 91%                        | 0%                            |
| 0.5%                  | 95%                        | 0%                            |
| 0.7%                  | 73%                        | 0%                            |
| 1%                    | 72%                        | 0%                            |
| 1.5%                  | 50%                        | 0%                            |
| 2%                    | 10%                        | 0%                            |
| 3%                    | 0%                         | 0%                            |

Without repair data, the message almost never survives once bits start flipping. With repair data, most messages survive up to about 1% bit-flip probability, and survival falls off steeply between 1.5% and 3%. The curve is not perfectly smooth at low intensities (for example 97% at 0.1% versus 99% at 0.2%), which is expected variation from 100 random trials per level.

## How to run

Requires Python 3.10 or newer.

```bash
git clone https://github.com/Ba-shha/Stowaway.git
cd Stowaway
pip install -r requirements.txt
```

```bash
streamlit run app.py                  # launch the app
python -m experiments.survival_curve  # regenerate the chart and CSV
pytest                                # run the tests
```

## Project structure

```
Stowaway/
├── app.py                    # Streamlit interface (Encode, Decode, Survival)
├── stowaway/
│   ├── crypto.py             # password -> key, lock / unlock (Fernet)
│   ├── repair.py             # Reed-Solomon protect / repair
│   ├── hide.py               # hide / reveal text in image LSBs
│   ├── storm.py              # NOAA fetch, cache, flux -> probability, damage
│   └── pipeline.py           # connects the stages: send / receive
├── experiments/
│   └── survival_curve.py     # survival experiment and chart
├── tests/                    # roundtrip, wrong password, tamper, repair, storm cache
├── assets/                   # space image and chart
├── data/noaa_cache.json      # last good NOAA reading (offline fallback)
└── results/survival_curve.csv
```

## Limitations and future work

* **The storm is a model.** Real proton flux sets the intensity, but the mapping to bit-flip probability (0.1 to 1,000 pfu mapped to 1e-6 to 1e-1 on a log scale) is our own choice, not a radiation-physics simulation. The damage step flips bits in all eight bit planes of the image, while the message lives only in the least significant bits.
* **LSB hiding breaks under JPEG, resizing or messaging apps.** The image must stay a lossless PNG.
* **LSB is easy to detect** with steganalysis tools, and the pixel positions used are fixed rather than password-dependent. Security comes from the encryption, not the hiding.
* **The length header is not separately protected.** Hidden text starts with a length header. If a storm damages that header, recovery fails even if the rest of the data is repairable.
* **Storm and spy are not always distinguishable.** An attacker who flips only a few bits will be silently repaired, exactly like a storm.
* **The tamper demo is staged.** We alter a byte ourselves to demonstrate authenticated encryption.
* **Capacity is limited** by image size and repair strength.

**Future work:** frequency-domain hiding that survives compression, a more physical radiation model, password-seeded scattering of bit positions, comparing several repair strengths, and stronger schemes for burst errors.

## Theme connection

Cosmo Polo carries knowledge across worlds. Stowaway is the traveller's hidden cargo: a message that crosses a watched, radiation-filled sky and arrives intact.

## AI disclosure

We used an AI assistant (Claude) for brainstorming, generating initial code, and explaining concepts. Our team chose the project direction, reviewed and tested all code, ran the experiments in `experiments/`, and wrote the results and limitations sections. Prompts and what we changed are logged in [`AI_USAGE.md`](https://claude.ai/chat/AI_USAGE.md).

## Team

| Person         | Owns                                      |
| -------------- | ----------------------------------------- |
| \<!-- name --> | \<!-- e.g. crypto.py, hide.py -->         |
| \<!-- name --> | \<!-- e.g. storm.py, repair.py -->        |
| \<!-- name --> | \<!-- e.g. experiments, tests -->         |
| \<!-- name --> | \<!-- e.g. app.py, README, demo video --> |

## Credits

* Space image: \<!-- TODO: NASA Webb/Hubble image title, credit line and source link -->
* Space weather data: [NOAA Space Weather Prediction Center](https://www.swpc.noaa.gov/) (GOES proton flux)
* Libraries: [Streamlit](https://streamlit.io/), [Pillow](https://python-pillow.org/), [NumPy](https://numpy.org/), [cryptography](https://cryptography.io/), [reedsolo](https://github.com/tomerfiliba-org/reedsolomon), [stegano](https://github.com/cedricbonhomme/Stegano), [requests](https://requests.readthedocs.io/), [Matplotlib](https://matplotlib.org/), [pytest](https://pytest.org/)

## License

MIT. See [LICENSE](https://claude.ai/chat/LICENSE).
