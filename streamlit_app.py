import os
from datetime import datetime
from typing import Dict

import streamlit as st

from silentwind.crypto import ScryptParams, CryptoError, encrypt_message, decrypt_message
from silentwind.storage import MessageStore, MessageRecord


APP_NAME = "SilentWind"
DEFAULT_DB_PATH = os.path.join("data", "silentwind.db")


def get_store(db_path: str) -> MessageStore:
    return MessageStore(db_path)


def record_to_decrypt_dict(rec: MessageRecord) -> Dict:
    return {
        "ciphertext": rec.ciphertext_b64,
        "nonce": rec.nonce_b64,
        "salt": rec.salt_b64,
        "aad": rec.aad_b64,
        "scheme": rec.scheme,
        "scrypt_n": rec.scrypt_n,
        "scrypt_r": rec.scrypt_r,
        "scrypt_p": rec.scrypt_p,
    }


def format_ts(ts: int) -> str:
    try:
        return datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return str(ts)


st.set_page_config(page_title=f"{APP_NAME} - E2E Messenger", page_icon="🕊️")

st.title("🕊️ SilentWind – End‑to‑end encrypted messenger")
st.caption("AES‑256‑GCM with scrypt key derivation. Messages are encrypted client‑side.")

with st.sidebar:
    st.subheader("Conversation settings")
    local_user = st.text_input("Your name", value=st.session_state.get("local_user", "Alice"))
    peer_user = st.text_input("Peer name", value=st.session_state.get("peer_user", "Bob"))
    shared_secret = st.text_input("Shared secret (passphrase)", type="password")

    with st.expander("Advanced (scrypt)"):
        n_exp = st.slider("N (2^x)", min_value=12, max_value=18, value=14, help="Work factor 2^x")
        scrypt_r = st.number_input("r", min_value=1, max_value=16, value=8)
        scrypt_p = st.number_input("p", min_value=1, max_value=8, value=1)
    params = ScryptParams(n=2 ** int(n_exp), r=int(scrypt_r), p=int(scrypt_p))

    db_path = st.text_input("Database path", value=st.session_state.get("db_path", DEFAULT_DB_PATH))
    col_a, col_b = st.columns(2)
    with col_a:
        refresh = st.button("Refresh")
    with col_b:
        st.session_state["local_user"] = local_user
        st.session_state["peer_user"] = peer_user
        st.session_state["db_path"] = db_path

if not local_user or not peer_user:
    st.info("Set both your name and the peer name to start.")
    st.stop()

store = get_store(db_path)

st.markdown(f"#### Conversation: `{local_user}` ⇄ `{peer_user}`")

# Load conversation
records = store.list_conversation(local_user, peer_user, limit=500)

# Show messages
for rec in records:
    role = "user" if rec.sender == local_user else "assistant"
    label = rec.sender
    with st.chat_message(role, avatar="🧑" if role == "user" else "👤"):
        if shared_secret:
            try:
                plaintext = decrypt_message(record_to_decrypt_dict(rec), shared_secret)
            except CryptoError:
                plaintext = "[Unable to decrypt – wrong secret or corrupted message]"
        else:
            plaintext = "[Enter shared secret to decrypt]"
        st.markdown(f"**{label}** · {format_ts(rec.created_ts)}")
        st.write(plaintext)

# Composer
user_input = st.chat_input("Type a message…")
if user_input:
    if not shared_secret:
        st.warning("Enter a shared secret to send an encrypted message.")
        st.stop()
    try:
        enc = encrypt_message(
            user_input,
            shared_secret,
            sender=local_user,
            recipient=peer_user,
            scrypt_params=params,
        )
        # Include addressing metadata for storage only
        enc["sender"] = local_user
        enc["recipient"] = peer_user
        store.add(enc)
        st.experimental_rerun()
    except CryptoError as e:
        st.error(f"Encryption error: {e}")
