import os
import sqlite3
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "football.db")


def get_db():
    """Open a SQLite connection with foreign keys enabled."""
    conn = sqlite3.connect(DATABASE)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create the three tables if they do not exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS teams (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS players (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT NOT NULL,
            position TEXT NOT NULL,
            team_id  INTEGER NOT NULL,
            FOREIGN KEY (team_id) REFERENCES teams(id)
        );
        CREATE TABLE IF NOT EXISTS player_stats (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id       INTEGER NOT NULL UNIQUE,
            matches         INTEGER,
            minutes         INTEGER,
            goals           INTEGER,
            assists         INTEGER,
            shots           INTEGER,
            shots_on_target INTEGER,
            passes          INTEGER,
            pass_accuracy   REAL,
            FOREIGN KEY (player_id) REFERENCES players(id)
        );
    """)
    conn.commit()
    conn.close()


def seed_from_csv(csv_name="players.csv"):
    """Load players.csv into the tables, only if they are empty."""
    conn = get_db()
    if conn.execute("SELECT COUNT(*) FROM players").fetchone()[0] > 0:
        conn.close()
        return
    df = pd.read_csv(os.path.join(BASE_DIR, csv_name))
    for team in df["Team"].unique():
        conn.execute("INSERT OR IGNORE INTO teams (name) VALUES (?)", (team,))
    for r in df.itertuples(index=False):
        team_id = conn.execute("SELECT id FROM teams WHERE name = ?", (r.Team,)).fetchone()[0]
        cur = conn.execute(
            "INSERT INTO players (name, position, team_id) VALUES (?, ?, ?)",
            (r.Player, r.Position, team_id))
        conn.execute(
            """INSERT INTO player_stats (player_id, matches, minutes, goals, assists,
               shots, shots_on_target, passes, pass_accuracy)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (cur.lastrowid, r.Matches, r.Minutes, r.Goals, r.Assists,
             r.Shots, r.Shots_On_Target, r.Passes, r.Pass_Accuracy))
    conn.commit()
    conn.close()


def load_players_df():
    """JOIN the three tables and return the same DataFrame read_csv gave before."""
    conn = get_db()
    df = pd.read_sql_query("""
        SELECT p.name AS Player, t.name AS Team, p.position AS Position,
               s.matches AS Matches, s.minutes AS Minutes, s.goals AS Goals,
               s.assists AS Assists, s.shots AS Shots,
               s.shots_on_target AS Shots_On_Target, s.passes AS Passes,
               s.pass_accuracy AS Pass_Accuracy
        FROM players p
        JOIN teams t        ON p.team_id = t.id
        JOIN player_stats s ON s.player_id = p.id
    """, conn)
    conn.close()
    return df


# ---------------------------------------------------------------------------
# Helpers used by the Flask web app (app.py)
# ---------------------------------------------------------------------------
# One SELECT that joins the 3 tables and adds the 4 derived columns in SQL.
PLAYER_SQL = """
    SELECT p.id AS id, p.name AS name, p.position AS position,
           t.id AS team_id, t.name AS team,
           s.matches, s.minutes, s.goals, s.assists, s.shots,
           s.shots_on_target, s.passes, s.pass_accuracy,
           ROUND(s.goals * 1.0 / s.matches, 2)               AS goals_per_match,
           CASE WHEN s.shots > 0
                THEN ROUND(s.shots_on_target * 100.0 / s.shots, 1)
                ELSE 0 END                                   AS shot_accuracy,
           s.goals + s.assists                               AS contributions,
           ROUND((s.goals + s.assists) * 1.0 / s.matches, 2) AS best_score
    FROM players p
    JOIN teams t        ON p.team_id = t.id
    JOIN player_stats s ON s.player_id = p.id
"""


def query(sql, args=(), one=False):
    """Run a SELECT and return rows that can be used like dictionaries."""
    conn = get_db()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    if one:
        return rows[0] if rows else None
    return rows


def _team_id(conn, team_name):
    conn.execute("INSERT OR IGNORE INTO teams (name) VALUES (?)", (team_name,))
    return conn.execute("SELECT id FROM teams WHERE name = ?", (team_name,)).fetchone()[0]


def add_player(d):
    conn = get_db()
    team_id = _team_id(conn, d["team"])
    cur = conn.execute("INSERT INTO players (name, position, team_id) VALUES (?, ?, ?)",
                       (d["name"], d["position"], team_id))
    conn.execute(
        """INSERT INTO player_stats (player_id, matches, minutes, goals, assists, shots,
           shots_on_target, passes, pass_accuracy) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (cur.lastrowid, d["matches"], d["minutes"], d["goals"], d["assists"], d["shots"],
         d["shots_on_target"], d["passes"], d["pass_accuracy"]))
    conn.commit()
    conn.close()
    return cur.lastrowid


def update_player(player_id, d):
    conn = get_db()
    team_id = _team_id(conn, d["team"])
    conn.execute("UPDATE players SET name = ?, position = ?, team_id = ? WHERE id = ?",
                 (d["name"], d["position"], team_id, player_id))
    conn.execute(
        """UPDATE player_stats SET matches = ?, minutes = ?, goals = ?, assists = ?, shots = ?,
           shots_on_target = ?, passes = ?, pass_accuracy = ? WHERE player_id = ?""",
        (d["matches"], d["minutes"], d["goals"], d["assists"], d["shots"],
         d["shots_on_target"], d["passes"], d["pass_accuracy"], player_id))
    conn.commit()
    conn.close()


def delete_player(player_id):
    conn = get_db()
    conn.execute("DELETE FROM player_stats WHERE player_id = ?", (player_id,))
    conn.execute("DELETE FROM players WHERE id = ?", (player_id,))
    conn.commit()
    conn.close()
