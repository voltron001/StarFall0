import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional


@dataclass(frozen=True)
class MessageRecord:
    id: int
    sender: str
    recipient: str
    ciphertext_b64: str
    nonce_b64: str
    salt_b64: str
    aad_b64: str
    scheme: str
    scrypt_n: int
    scrypt_r: int
    scrypt_p: int
    created_ts: int


class MessageStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._ensure_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_db(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    ciphertext_b64 TEXT NOT NULL,
                    nonce_b64 TEXT NOT NULL,
                    salt_b64 TEXT NOT NULL,
                    aad_b64 TEXT NOT NULL,
                    scheme TEXT NOT NULL,
                    scrypt_n INTEGER NOT NULL,
                    scrypt_r INTEGER NOT NULL,
                    scrypt_p INTEGER NOT NULL,
                    created_ts INTEGER NOT NULL
                );
                """
            )
            conn.commit()

    def add(self, encrypted_record: Dict) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO messages (
                    sender, recipient, ciphertext_b64, nonce_b64, salt_b64,
                    aad_b64, scheme, scrypt_n, scrypt_r, scrypt_p, created_ts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, strftime('%s','now'))
                """,
                (
                    encrypted_record.get("sender", ""),
                    encrypted_record.get("recipient", ""),
                    encrypted_record["ciphertext"],
                    encrypted_record["nonce"],
                    encrypted_record["salt"],
                    encrypted_record.get("aad", ""),
                    encrypted_record.get("scheme", ""),
                    int(encrypted_record.get("scrypt_n", 0)),
                    int(encrypted_record.get("scrypt_r", 0)),
                    int(encrypted_record.get("scrypt_p", 0)),
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def list_conversation(self, user_a: str, user_b: str, limit: int = 100) -> List[MessageRecord]:
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT * FROM messages
                WHERE (sender = ? AND recipient = ?) OR (sender = ? AND recipient = ?)
                ORDER BY created_ts ASC, id ASC
                LIMIT ?
                """,
                (user_a, user_b, user_b, user_a, limit),
            )
            rows = cur.fetchall()
            return [
                MessageRecord(
                    id=row["id"],
                    sender=row["sender"],
                    recipient=row["recipient"],
                    ciphertext_b64=row["ciphertext_b64"],
                    nonce_b64=row["nonce_b64"],
                    salt_b64=row["salt_b64"],
                    aad_b64=row["aad_b64"],
                    scheme=row["scheme"],
                    scrypt_n=row["scrypt_n"],
                    scrypt_r=row["scrypt_r"],
                    scrypt_p=row["scrypt_p"],
                    created_ts=row["created_ts"],
                )
                for row in rows
            ]

    def list_users(self) -> List[str]:
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT DISTINCT sender AS user FROM messages
                UNION
                SELECT DISTINCT recipient AS user FROM messages
                ORDER BY user ASC
                """
            )
            return [row[0] for row in cur.fetchall() if row[0]]
