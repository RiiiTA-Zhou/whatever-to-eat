import glob
import json
import sqlite3
import os


def init_db(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            tastes TEXT NOT NULL DEFAULT '[]',
            dislikes TEXT NOT NULL DEFAULT '[]',
            avoid TEXT NOT NULL DEFAULT '[]',
            difficulty_preference INTEGER DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS recent_meals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            date TEXT NOT NULL,
            dish TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_recent_meals_user_date
            ON recent_meals(user_id, date DESC);
    """)
    conn.commit()


def migrate(db_path: str = "./user_memory/whatever_to_eat.db", json_dir: str = "./users_history"):
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(db_path)
    init_db(conn)

    json_files = glob.glob(os.path.join(json_dir, "*.json"))
    success = 0
    errors = []

    for fpath in sorted(json_files):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)

            user_id = data.get("user_id", os.path.splitext(os.path.basename(fpath))[0])
            prefs = data.get("preferences", {})
            recent_meals = data.get("recent_meals", [])

            conn.execute(
                """INSERT OR REPLACE INTO users
                   (user_id, tastes, dislikes, avoid, difficulty_preference)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    user_id,
                    json.dumps(prefs.get("tastes", []), ensure_ascii=False),
                    json.dumps(prefs.get("dislikes", []), ensure_ascii=False),
                    json.dumps(prefs.get("avoid", []), ensure_ascii=False),
                    prefs.get("difficulty_preference"),
                ),
            )

            if recent_meals:
                conn.executemany(
                    "INSERT INTO recent_meals (user_id, date, dish) VALUES (?, ?, ?)",
                    [(user_id, m["date"], m["dish"]) for m in recent_meals],
                )

            success += 1
            print(f"  OK: {user_id} ({len(recent_meals)} meals)")
        except Exception as e:
            errors.append((fpath, str(e)))
            print(f"  FAIL: {os.path.basename(fpath)} - {e}")

    conn.commit()
    conn.close()

    print(f"\n完成: {success}/{len(json_files)} 个用户导入成功")
    if errors:
        print(f"失败: {len(errors)} 个")
        for fpath, err in errors:
            print(f"  - {os.path.basename(fpath)}: {err}")


if __name__ == "__main__":
    migrate()
