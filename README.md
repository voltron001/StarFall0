# 🕊️ SilentWind – End‑to‑end encrypted messenger

SilentWind is a minimal end‑to‑end encrypted chat built with Streamlit and Python. 
It uses AES‑256‑GCM for authenticated encryption, with keys derived from a shared passphrase using scrypt.

- **Cipher**: AES‑256‑GCM (via `cryptography`)
- **Key derivation**: scrypt (unique salt per message)
- **Storage**: SQLite – only ciphertext and crypto metadata are stored (no plaintext)

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## How it works

- Enter your name, your peer’s name, and a shared secret in the sidebar.
- Messages are encrypted client‑side using a fresh random salt and nonce per message.
- Additional authenticated data (AAD) binds sender, recipient, and timestamp to each message.
- The database persists only ciphertext and metadata; decryption happens only on the client with your secret.

## Security notes

This app demonstrates core E2E concepts but is not a full production system.
For real deployments you would add key exchange, message authentication of identities, forward secrecy, and secure secret handling.
