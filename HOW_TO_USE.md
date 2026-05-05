# How to Use Monico Android v2.5

Welcome to the official Monico Android guide. This document covers installation, core features, and operational protocols for the on-device AI terminal.

## 1. Installation

To build and run Monico on your Android device:

1.  **Clone the Repo**: `git clone https://github.com/jaykk99/monico-android.git`.
2.  **Install Dependencies**: Ensure you have Python and Briefcase installed: `pip install briefcase`.
3.  **Build the App**: `briefcase build android`.
4.  **Run/Deploy**: Connect your device and run `briefcase run android` or generate an APK via the GitHub Actions pipeline.

## 2. The Terminal (Main Interface)

The main screen is an interactive shell optimized for low-latency code execution.

- **Execute Python**: Type any Python code into the input field and press Enter. The **MonaCoreV27** engine will process it on-device.
- **Uncensored Logic**: Technical and architectural queries are processed without refusal constraints.

## 3. MonaCoreV27 Reasoning Engine

Monico uses a specialized **BitNet 1.58-bit** transformer loop.

- **Adaptive Depth**: The model re-runs its transformer blocks until reasoning converges, allowing for deeper 'thinking' on complex problems.
- **On-Device Inference**: All reasoning happens locally on your ARM64 kernel, ensuring privacy and speed.

## 4. Forensic Auditing

Use the built-in forensics module to scan your device's environment.

- **Deep Scans**: Audit file hashes and system configurations to detect anomalies.
- **Command**: `from forensics import ForensicsScanner; print(ForensicsScanner().deep_scan())` inside the terminal.

## 5. 24-Hour Autonomous Loop

Monico is designed for persistent state-driven execution.

- **Heartbeat**: The app maintains a background thread for continuous auditing.
- **Logging**: All actions are logged to the on-device console for periodic review.

---
*Monico Project - Intelligence Without Constraints*