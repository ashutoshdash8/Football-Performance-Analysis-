import os
from flask import Flask, render_template, request, redirect, url_for, flash, abort

import database as db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")

POSITIONS = ["Forward", "Midfielder", "Defender", "Goalkeeper"]

INT_FIELDS = ["matches", "minutes", "goals", "assists", "shots", "shots_on_target", "passes"]


def read_form(form):
    """Validate the add/edit form. Returns (data, errors)."""
    d, errors = {}, []
    d["name"] = form.get("name", "").strip()
    d["position"] = form.get("position", "")
    new_team = form.get("new_team", "").strip()
    d["team"] = new_team or form.get("team", "").strip()

    if not d["name"]:
        errors.append("Player name is required.")
    if d["position"] not in POSITIONS:
        errors.append("Choose a valid position.")
    if not d["team"]:
        errors.append("Choose a team or type a new one.")

    for f in INT_FIELDS:
        try:
            d[f] = int(form.get(f, ""))
            if d[f] < 0:
                raise ValueError
        except ValueError:
            d[f] = 0
            errors.append(f"{f.replace('_', ' ').title()} must be a whole number (0 or more).")
    try:
        d["pass_accuracy"] = float(form.get("pass_accuracy", ""))
        if not 0 <= d["pass_accuracy"] <= 100:
            raise ValueError
    except ValueError:
        d["pass_accuracy"] = 0
        errors.append("Pass accuracy must be between 0 and 100.")

    if d["matches"] < 1 and not any("Matches" in e for e in errors):
        errors.append("Matches must be at least 1.")
    if d["shots_on_target"] > d["shots"]:
        errors.append("Shots on target cannot be more than total shots.")
    return d, errors


@app.route("/")
def dashboard():
    totals = db.query("""
        SELECT COUNT(*) AS players, SUM(goals) AS goals, SUM(assists) AS assists,
               SUM(shots) AS shots, ROUND(AVG(pass_accuracy), 1) AS pass_acc
        FROM player_stats""", one=True)
    team_count = db.query("SELECT COUNT(*) AS n FROM teams", one=True)["n"]
    best = db.query(db.PLAYER_SQL + " ORDER BY best_score DESC, goals DESC LIMIT 5")
    scorers = db.query(db.PLAYER_SQL + " ORDER BY s.goals DESC, p.name LIMIT 5")
    teams = db.query("""
        SELECT t.name AS name, COUNT(p.id) AS players, SUM(s.goals) AS goals,
               SUM(s.assists) AS assists, SUM(s.shots) AS shots
        FROM teams t JOIN players p ON p.team_id = t.id
        JOIN player_stats s ON s.player_id = p.id
        GROUP BY t.id ORDER BY goals DESC, t.name""")
    positions = db.query("""
        SELECT p.position AS position, COUNT(*) AS n, ROUND(AVG(s.pass_accuracy), 1) AS pass_acc
        FROM players p JOIN player_stats s ON s.player_id = p.id GROUP BY p.position""")
    pos = {r["position"]: r for r in positions}
    corr = None
    rows = db.query("SELECT shots, goals FROM player_stats")
    if len(rows) > 1:
        xs, ys = [r["shots"] for r in rows], [r["goals"] for r in rows]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        sxx = sum((x - mx) ** 2 for x in xs)
        syy = sum((y - my) ** 2 for y in ys)
        if sxx and syy:
            corr = round(sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sxx * syy) ** 0.5, 2)
    return render_template("dashboard.html", totals=totals, team_count=team_count, best=best,
                           scorers=scorers, teams=teams, pos=pos, positions=POSITIONS, corr=corr,
                           max_goals=max([t["goals"] for t in teams] or [1]) or 1,
                           max_scorer=max([s["goals"] for s in scorers] or [1]) or 1)


@app.route("/players")
def players():
    q = request.args.get("q", "").strip()
    team = request.args.get("team", "")
    position = request.args.get("position", "")
    sort = request.args.get("sort", "goals")
    sort_cols = {"goals": "s.goals DESC", "score": "best_score DESC", "name": "p.name",
                 "assists": "s.assists DESC", "pass": "s.pass_accuracy DESC"}
    sql, args = db.PLAYER_SQL + " WHERE 1=1", []
    if q:
        sql += " AND p.name LIKE ?"
        args.append(f"%{q}%")
    if team:
        sql += " AND t.name = ?"
        args.append(team)
    if position:
        sql += " AND p.position = ?"
        args.append(position)
    sql += " ORDER BY " + sort_cols.get(sort, "s.goals DESC") + ", p.name"
    rows = db.query(sql, args)
    teams = db.query("SELECT name FROM teams ORDER BY name")
    return render_template("players.html", players=rows, teams=teams, positions=POSITIONS,
                           q=q, team=team, position=position, sort=sort)


def team_choices():
    return [r["name"] for r in db.query("SELECT name FROM teams ORDER BY name")]


@app.route("/players/add", methods=["GET", "POST"])
def add_player():
    data = {"pass_accuracy": "", "position": "Forward", "team": ""}
    if request.method == "POST":
        data, errors = read_form(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            db.add_player(data)
            flash(f"{data['name']} was added to {data['team']}.", "success")
            return redirect(url_for("players"))
        data = request.form.to_dict()
        data["team"] = request.form.get("team", "")
    return render_template("player_form.html", p=data, teams=team_choices(),
                           positions=POSITIONS, mode="add")


@app.route("/players/<int:pid>/edit", methods=["GET", "POST"])
def edit_player(pid):
    row = db.query(db.PLAYER_SQL + " WHERE p.id = ?", (pid,), one=True)
    if row is None:
        abort(404)
    if request.method == "POST":
        data, errors = read_form(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
            data = request.form.to_dict()
            data["team"] = request.form.get("team", "")
            return render_template("player_form.html", p=data, teams=team_choices(),
                                   positions=POSITIONS, mode="edit", pid=pid)
        db.update_player(pid, data)
        flash(f"{data['name']} was updated.", "success")
        return redirect(url_for("players"))
    return render_template("player_form.html", p=dict(row), teams=team_choices(),
                           positions=POSITIONS, mode="edit", pid=pid)


@app.route("/players/<int:pid>/delete", methods=["POST"])
def delete_player(pid):
    row = db.query("SELECT name FROM players WHERE id = ?", (pid,), one=True)
    if row is None:
        abort(404)
    db.delete_player(pid)
    flash(f"{row['name']} was deleted.", "success")
    return redirect(url_for("players"))


@app.route("/teams")
def teams():
    rows = db.query("""
        SELECT t.id AS id, t.name AS name, COUNT(p.id) AS players, SUM(s.goals) AS goals,
               SUM(s.assists) AS assists, SUM(s.shots) AS shots,
               SUM(s.shots_on_target) AS sot, ROUND(AVG(s.pass_accuracy), 1) AS pass_acc
        FROM teams t JOIN players p ON p.team_id = t.id
        JOIN player_stats s ON s.player_id = p.id
        GROUP BY t.id ORDER BY goals DESC, t.name""")
    squads = {r["id"]: db.query(db.PLAYER_SQL + " WHERE t.id = ? ORDER BY s.goals DESC", (r["id"],))
              for r in rows}
    return render_template("teams.html", teams=rows, squads=squads)


@app.route("/rankings")
def rankings():
    rows = db.query(db.PLAYER_SQL + " ORDER BY best_score DESC, goals DESC")
    top = rows[0]["best_score"] if rows else 1
    return render_template("rankings.html", players=rows, top=top or 1)


if __name__ == "__main__":
    db.init_db()
    db.seed_from_csv()
    app.run(debug=True)
