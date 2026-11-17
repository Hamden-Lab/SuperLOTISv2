"""
Accelerometer Fourier / FFT Analysis

Input CSV format:

time_us,ax1_mps2,ay1_mps2,az1_mps2,ax2_mps2,ay2_mps2,az2_mps2

The script:
    1. Loads accelerometer data
    2. Determines sampling frequency from time_us
    3. Removes DC offset
    4. Applies a Hann window
    5. Computes a one-sided FFT
    6. Plots time-domain acceleration
    7. Plots frequency-domain amplitude spectrum
    8. Reports dominant frequencies
    9. Saves FFT results to CSV
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path


# ============================================================
# Configuration
# ============================================================

# Change this to your data file
INPUT_FILE = r"C:\Users\superlotis\Documents\GitHub\SuperLOTISv2\superlotis\data\2026-11-05T18-46-29.373549+00-00_accelerometer_data.csv"

# Number of strongest frequencies to report
N_PEAKS = 10

# Ignore frequencies below this value when searching for peaks.
# Set to 0 if you want to include DC / very-low-frequency content.
MIN_PEAK_FREQUENCY_HZ = 0.01


# ============================================================
# Load data
# ============================================================

print(f"Loading: {INPUT_FILE}")

df = pd.read_csv(INPUT_FILE)

required_columns = [
    "time_us",
    "ax1_mps2",
    "ay1_mps2",
    "az1_mps2",
    "ax2_mps2",
    "ay2_mps2",
    "az2_mps2",
]

for column in required_columns:
    if column not in df.columns:
        raise ValueError(f"Missing column: {column}")

# Remove rows containing invalid values
df = df.dropna(subset=required_columns)
df["aM1"] = np.sqrt((df["ax1_mps2"]-df["ax1_mps2"].mean())**2 + (df["ay1_mps2"]-df["ay1_mps2"].mean())**2 + (df["az1_mps2"]-df["az1_mps2"].mean())**2)
df["aM2"] = np.sqrt((df["ax2_mps2"]-df["ax2_mps2"].mean())**2 + (df["ay2_mps2"]-df["ay2_mps2"].mean())**2 + (df["az2_mps2"]-df["az2_mps2"].mean())**2)

time_us = df["time_us"].to_numpy(dtype=float)

# Convert microseconds to seconds
time_s = (time_us - time_us[0]) / 1e6

N = len(time_s)

if N < 4:
    raise ValueError("Not enough samples for FFT analysis.")


# ============================================================
# Determine sampling frequency
# ============================================================

dt = np.diff(time_s)

sample_period = np.median(dt)
fs = 1.0 / sample_period

print()
print("========================================")
print("Sampling information")
print("========================================")
print(f"Number of samples : {N}")
print(f"Sample period     : {sample_period:.6f} s")
print(f"Sampling frequency : {fs:.3f} Hz")
print(f"Nyquist frequency : {fs / 2:.3f} Hz")
print(f"Total duration    : {time_s[-1]:.3f} s")
print(f"Frequency resolution: {fs / N:.4f} Hz")


# Check for irregular sampling
jitter = np.std(dt)

if jitter > sample_period * 0.01:
    print()
    print("WARNING: Sampling interval is not very uniform.")
    print(f"Standard deviation of dt: {jitter:.6e} s")


# ============================================================
# FFT function
# ============================================================

def calculate_fft(signal, fs):
    """
    Calculate a one-sided amplitude FFT.

    Returns:
        frequencies
        amplitude
    """

    signal = np.asarray(signal, dtype=float)

    N = len(signal)

    # Remove mean / DC component
    signal = signal - np.mean(signal)

    # Hann window
    window = np.hanning(N)

    windowed_signal = signal * window

    # FFT
    fft_result = np.fft.rfft(windowed_signal)

    frequencies = np.fft.rfftfreq(N, d=1.0 / fs)

    # Amplitude correction for Hann window
    amplitude = (2.0 / np.sum(window)) * np.abs(fft_result)

    # DC should not be doubled
    amplitude[0] /= 2

    return frequencies, amplitude


# ============================================================
# Accelerometer channels
# ============================================================

channels = {
    "Accel 1 X": "ax1_mps2",
    "Accel 1 Y": "ay1_mps2",
    "Accel 1 Z": "az1_mps2",
    "Accel 2 X": "ax2_mps2",
    "Accel 2 Y": "ay2_mps2",
    "Accel 2 Z": "az2_mps2",

}


# ============================================================
# Calculate FFTs
# ============================================================

fft_results = {}

for name, column in channels.items():

    signal = df[column].to_numpy(dtype=float)

    frequencies, amplitude = calculate_fft(signal, fs)

    fft_results[name] = {
        "frequency_hz": frequencies,
        "amplitude_mps2": amplitude,
    }



fft_results["Accel 1 Mag"] = {"frequency_hz": fft_results[name]["frequency_hz"], "amplitude_mps2": np.sqrt((fft_results["Accel 1 X"]["amplitude_mps2"])**2 + (fft_results["Accel 1 Y"]["amplitude_mps2"])**2 + (fft_results["Accel 1 Z"]["amplitude_mps2"])**2)}

fft_results["Accel 2 Mag"] = {"frequency_hz": fft_results[name]["frequency_hz"], "amplitude_mps2": np.sqrt((fft_results["Accel 2 X"]["amplitude_mps2"])**2 + (fft_results["Accel 2 Y"]["amplitude_mps2"])**2 + (fft_results["Accel 2 Z"]["amplitude_mps2"])**2)}



# ============================================================
# Find dominant frequencies
# ============================================================

print()
print("========================================")
print("Dominant frequencies")
print("========================================")

for name, result in fft_results.items():

    frequencies = result["frequency_hz"]
    amplitude = result["amplitude_mps2"]

    # Ignore very low frequencies
    valid = frequencies >= MIN_PEAK_FREQUENCY_HZ

    valid_frequencies = frequencies[valid]
    valid_amplitude = amplitude[valid]

    # Sort by amplitude
    indices = np.argsort(valid_amplitude)[::-1]

    print()
    print(name)
    print("-" * 30)

    reported = 0

    for index in indices:

        frequency = valid_frequencies[index]
        amp = valid_amplitude[index]

        # Skip zero-amplitude bins
        if amp <= 0:
            continue

        print(
            f"{frequency:8.3f} Hz   "
            f"{amp:10.5f} m/s²"
        )

        reported += 1

        if reported >= N_PEAKS:
            break


df["time_s"] = df["time_us"]*1e6
df.sort_values("time_s", inplace=True)

# ============================================================
# Plot time-domain signals
# ============================================================

fig, axes = plt.subplots(
    2,
    1,
    figsize=(12, 8),
    sharex=True
)

# Accelerometer 1
axes[0].plot(
    df["time_s"],
    df["ax1_mps2"],
    label="X"
)

axes[0].plot(
    df["time_s"],
    df["ay1_mps2"],
    label="Y"
)

axes[0].plot(
    df["time_s"],
    df["az1_mps2"],
    label="Z"
)

axes[0].plot(
    df["time_s"],
    df["aM1"],
    label="Mag",
    color="k"
)

axes[0].set_title("Accelerometer 1 - Time Domain")
axes[0].set_ylabel("Acceleration (m/s²)")
axes[0].grid(True)
axes[0].legend()


# Accelerometer 2
axes[1].plot(
    df["time_s"],
    df["ax2_mps2"],
    label="X"
)

axes[1].plot(
    df["time_s"],
    df["ay2_mps2"],
    label="Y"
)

axes[1].plot(
    df["time_s"],
    df["az2_mps2"],
    label="Z"
)

axes[1].plot(
    df["time_s"],
    df["aM2"],
    label="Mag",
    color="k"
)

axes[1].set_title("Accelerometer 2 - Time Domain")
axes[1].set_xlabel("Time (s)")
axes[1].set_ylabel("Acceleration (m/s²)")
axes[1].grid(True)
axes[1].legend()

plt.tight_layout()

# plt.savefig(
#     INPUT_FILE.parent / f"{INPUT_FILE.stem}_time_domain.png",
#     dpi=200
# )


# ============================================================
# Plot FFT
# ============================================================

fig, axes = plt.subplots(
    2,
    1,
    figsize=(12, 10),
    sharex=True
)


# Accelerometer 1
for axis, color in zip(
    ["X", "Y", "Z", "Mag"],
    ["tab:red", "tab:green", "tab:blue", "k"]
):

    name = f"Accel 1 {axis}"

    axes[0].plot(
        fft_results[name]["frequency_hz"],
        fft_results[name]["amplitude_mps2"],
        label=axis,
        color=color
    )

axes[0].set_title("Accelerometer 1 - Fourier Spectrum")
axes[0].set_ylabel("Amplitude (m/s²)")
axes[0].grid(True)
axes[0].legend()


# Accelerometer 2
for axis, color in zip(
    ["X", "Y", "Z", "Mag"],
    ["tab:red", "tab:green", "tab:blue", "k"]
):

    name = f"Accel 2 {axis}"

    axes[1].plot(
        fft_results[name]["frequency_hz"],
        fft_results[name]["amplitude_mps2"],
        label=axis,
        color=color
    )

axes[1].set_title("Accelerometer 2 - Fourier Spectrum")
axes[1].set_xlabel("Frequency (Hz)")
axes[1].set_ylabel("Amplitude (m/s²)")
axes[1].grid(True)
axes[1].legend()


# Nyquist limit
axes[1].axvline(
    fs / 2,
    color="black",
    linestyle="--",
    alpha=0.5,
    label="Nyquist"
)

plt.tight_layout()

# fft_plot_file = (
#     INPUT_FILE.parent /
#     f"{INPUT_FILE.stem}_fft.png"
# )

# plt.savefig(
#     fft_plot_file,
#     dpi=200
# )

# print()
# print(f"Saved FFT plot: {fft_plot_file}")


# ============================================================
# Save FFT results
# ============================================================

fft_df = pd.DataFrame({
    "frequency_hz": fft_results["Accel 1 X"]["frequency_hz"],

    "ax1_amplitude_mps2":
        fft_results["Accel 1 X"]["amplitude_mps2"],

    "ay1_amplitude_mps2":
        fft_results["Accel 1 Y"]["amplitude_mps2"],

    "az1_amplitude_mps2":
        fft_results["Accel 1 Z"]["amplitude_mps2"],

    "ax2_amplitude_mps2":
        fft_results["Accel 2 X"]["amplitude_mps2"],

    "ay2_amplitude_mps2":
        fft_results["Accel 2 Y"]["amplitude_mps2"],

    "az2_amplitude_mps2":
        fft_results["Accel 2 Z"]["amplitude_mps2"],

    "M1":
        fft_results["Accel 1 Mag"]["amplitude_mps2"],

    "M2":
        fft_results["Accel 2 Mag"]["amplitude_mps2"],
})




# fft_output_file = (
#     INPUT_FILE.parent /
#     f"{INPUT_FILE.stem}_fft.csv"
# )

# fft_df.to_csv(
#     fft_output_file,
#     index=False
# )

# print(f"Saved FFT data : {fft_output_file}")

print()
print("Analysis complete.")

plt.show()





# ============================================================
# Plot FFT Amplitude Ratios (Accelerometer 1 / 2)
# ============================================================


axis_names = ["Mag"]


fig, axes = plt.subplots(
    len(axis_names),
    1,
    figsize=(12, 12),
    sharex=True
)

for i, axis in enumerate(axis_names):

    name1 = f"Accel 1 {axis}"
    name2 = f"Accel 2 {axis}"

    freq = fft_results[name1]["frequency_hz"]

    amp1 = fft_results[name1]["amplitude_mps2"]
    amp2 = fft_results[name2]["amplitude_mps2"]

    # Avoid division by zero
    ratio = np.divide(
        amp1,
        amp2,
        out=np.full_like(amp1, np.nan),
        where=amp2 > 0
    )

    axes.plot(
        freq,
        ratio,
        label=f"Accel 1 / Accel 2 ({axis})",
        color=["tab:red", "tab:green", "tab:blue", "black"][i]
    )

    # Reference ratio = 1
    axes.axhline(
        1.0,
        color="gray",
        linestyle="--",
        alpha=0.7
    )

    axes.set_title(f"{axis} Amplitude Ratio")
    axes.set_ylabel("Amplitude Ratio")
    axes.grid(True)
    axes.legend()

axes.set_xlabel("Frequency (Hz)")

plt.tight_layout()

plt.show()