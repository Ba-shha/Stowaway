# Generates the survival curve chart and CSV
"""
experiments/survival_curve.py

Benchmarking script for Project Stowaway.
Simulates radiation bit-flips across solar storm intensities to generate
a survival curve comparing payload recovery rates WITH vs WITHOUT Reed-Solomon ECC.
Outputs the benchmark chart to assets/survival_curve.png.
"""

import os
import random
import matplotlib.pyplot as plt
from stowaway.crypto import lock, unlock
from stowaway.repair import protect, repair


def simulate_bit_flips(data: bytes, bit_flip_prob: float) -> bytes:
    """Simulates space radiation damage by flipping bits with a given probability."""
    data_arr = bytearray(data)
    for i in range(len(data_arr)):
        for bit in range(8):
            if random.random() < bit_flip_prob:
                data_arr[i] ^= (1 << bit)
    return bytes(data_arr)


def run_experiment(num_trials: int = 100):
    # Ensure assets directory exists
    os.makedirs("assets", exist_ok=True)

    message = "Stowaway Deep Space Telemetry Data Alpha-7"
    password = "space-passphrase-2026"
    nsym = 32

    # Bit-flip probabilities ranging from 0.0% to 1.5%
    probabilities = [i * 0.001 for i in range(16)]

    ecc_survival = []
    raw_survival = []

    print("--- Running Radiation Survival Curve Benchmark ---")

    for p in probabilities:
        ecc_successes = 0
        raw_successes = 0

        for _ in range(num_trials):
            # 1. Encrypt raw payload
            salt, token = lock(message, password)

            # --- Test WITH Reed-Solomon ECC ---
            protected = protect(token, nsym=nsym)
            corrupted_protected = simulate_bit_flips(protected, p)
            try:
                repaired_token = repair(corrupted_protected, nsym=nsym)
                decrypted = unlock(repaired_token, password, salt)
                if decrypted == message:
                    ecc_successes += 1
            except Exception:
                pass

            # --- Test WITHOUT ECC (Raw Token) ---
            corrupted_raw = simulate_bit_flips(token, p)
            try:
                decrypted_raw = unlock(corrupted_raw, password, salt)
                if decrypted_raw == message:
                    raw_successes += 1
            except Exception:
                pass

        ecc_rate = (ecc_successes / num_trials) * 100
        raw_rate = (raw_successes / num_trials) * 100

        ecc_survival.append(ecc_rate)
        raw_survival.append(raw_rate)

        print(f"Bit Flip Prob: {p*100:4.2f}% | ECC Survival: {ecc_rate:5.1f}% | Raw Survival: {raw_rate:5.1f}%")

    # Generate graph
    plt.style.use('dark_background')
    plt.figure(figsize=(10, 6))

    plt.plot([p * 100 for p in probabilities], ecc_survival, marker='o', linewidth=2.5, color='#00FFCC', label='With Reed-Solomon ECC (nsym=32)')
    plt.plot([p * 100 for p in probabilities], raw_survival, marker='x', linewidth=2.5, color='#FF5555', linestyle='--', label='Without ECC (Raw Encryption)')

    plt.title('Payload Survival Rate vs. Solar Storm Bit-Flip Probability', fontsize=14, pad=15)
    plt.xlabel('Bit-Flip Error Probability (%)', fontsize=12)
    plt.ylabel('Payload Recovery Success Rate (%)', fontsize=12)
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(fontsize=11)
    plt.ylim(-5, 105)

    output_path = os.path.join("assets", "survival_curve.png")
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"\n[SUCCESS] Benchmark complete! Chart saved to: {output_path}")


if __name__ == "__main__":
    run_experiment()
