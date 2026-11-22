import json
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "farmup.db")
DEFAULT_SEED_JSON = os.path.join(BASE_DIR, "data", "msp_rates.json")


def init_msp_table(db_path=DEFAULT_DB_PATH, seed_json_path=DEFAULT_SEED_JSON):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS msp_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            crop TEXT NOT NULL,
            aliases_json TEXT NOT NULL,
            season TEXT NOT NULL,
            msp_per_quintal REAL NOT NULL,
            region_required INTEGER NOT NULL DEFAULT 0,
            region_note TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(crop, season)
        )
        """
    )
    conn.commit()

    count = cur.execute("SELECT COUNT(*) FROM msp_rates").fetchone()[0]
    if count == 0 and os.path.exists(seed_json_path):
        seed_msp_from_json(seed_json_path, db_path=db_path, conn=conn)

    conn.close()


def seed_msp_from_json(json_path=DEFAULT_SEED_JSON, db_path=DEFAULT_DB_PATH, conn=None):
    with open(json_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    own_conn = conn is None
    if own_conn:
        conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    saved = 0
    for item in items:
        crop = str(item.get("crop", "")).strip()
        season = str(item.get("season", "")).strip()
        msp_val = item.get("msp_per_quintal")
        if not crop or not season or msp_val is None:
            continue

        aliases = [str(a).strip() for a in (item.get("aliases") or []) if str(a).strip()]
        region_required = 1 if item.get("region_required") else 0
        region_note = str(item.get("region_note", "")).strip()

        cur.execute(
            """
            INSERT INTO msp_rates
                (crop, aliases_json, season, msp_per_quintal, region_required, region_note, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(crop, season)
            DO UPDATE SET
                aliases_json = excluded.aliases_json,
                msp_per_quintal = excluded.msp_per_quintal,
                region_required = excluded.region_required,
                region_note = excluded.region_note,
                updated_at = CURRENT_TIMESTAMP
            """,
            (crop, json.dumps(aliases), season, float(msp_val), region_required, region_note),
        )
        saved += 1

    conn.commit()
    if own_conn:
        conn.close()
    return saved


def search_msp(crop_query, db_path=DEFAULT_DB_PATH):
    init_msp_table(db_path=db_path)
    q = (crop_query or "").strip().lower()
    if not q:
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT crop, aliases_json, season, msp_per_quintal, region_required, region_note FROM msp_rates ORDER BY id ASC"
    ).fetchall()
    conn.close()

    matches = []
    for r in rows:
        try:
            aliases = json.loads(r["aliases_json"] or "[]")
        except json.JSONDecodeError:
            aliases = []

        candidates = [r["crop"].lower()] + [str(a).lower() for a in aliases]
        if any(q in c or c in q for c in candidates):
            matches.append(
                {
                    "crop": r["crop"],
                    "season": r["season"],
                    "msp_per_quintal": r["msp_per_quintal"],
                    "region_required": bool(r["region_required"]),
                    "region_note": r["region_note"],
                }
            )
    return matches


if __name__ == "__main__":
    init_msp_table()
    total = seed_msp_from_json()
    print(f"Seeded/updated {total} MSP records into {DEFAULT_DB_PATH}.")