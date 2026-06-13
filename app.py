import copy
import os
import random
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")

APP_PASSWORD = os.environ.get("APP_PASSWORD")

if not app.secret_key:
    raise RuntimeError("SECRET_KEYが設定されていません。")

if not APP_PASSWORD:
    raise RuntimeError("APP_PASSWORDが設定されていません。")


players = []
current_player_index = 0
game_started = False
winner_message = ""
game_history = []


def reset_game_status():
    global current_player_index, game_started, winner_message

    current_player_index = 0
    game_started = False
    winner_message = ""
    game_history.clear()

    for player in players:
        player["score"] = 0
        player["miss_count"] = 0
        player["is_lost"] = False


def save_history():
    game_history.append({
        "players": copy.deepcopy(players),
        "current_player_index": current_player_index,
        "game_started": game_started,
        "winner_message": winner_message
    })


def restore_last_history():
    global current_player_index, game_started, winner_message

    if len(game_history) == 0:
        return False

    snapshot = game_history.pop()

    players.clear()
    players.extend(snapshot["players"])

    current_player_index = snapshot["current_player_index"]
    game_started = snapshot["game_started"]
    winner_message = snapshot["winner_message"]

    return True


def get_active_players():
    active_players = []

    for player in players:
        if not player["is_lost"]:
            active_players.append(player)

    return active_players


def get_ranking():
    return sorted(
        players,
        key=lambda player: (player["is_lost"], -player["score"], player["miss_count"])
    )


def update_score(player, point):
    if point == 0:
        player["miss_count"] += 1
    else:
        player["miss_count"] = 0

    if player["miss_count"] >= 3:
        player["is_lost"] = True
        return

    player["score"] += point

    if player["score"] > 50:
        player["score"] = 25


def check_winner(player):
    return player["score"] == 50


def move_to_next_player():
    global current_player_index

    if len(players) == 0:
        return

    current_player_index = (current_player_index + 1) % len(players)


@app.route("/")
def index():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    current_player = None
    ranking = []

    if game_started and len(players) > 0 and not winner_message:
        current_player = players[current_player_index]

    if winner_message:
        ranking = get_ranking()

    return render_template(
        "index.html",
        players=players,
        game_started=game_started,
        current_player=current_player,
        winner_message=winner_message,
        ranking=ranking,
        can_undo=len(game_history) > 0
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    error_message = ""

    if request.method == "POST":
        password = request.form.get("password")

        if password == APP_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))
        else:
            error_message = "パスワードが違います。"

    return render_template("login.html", error_message=error_message)


@app.route("/add_player", methods=["POST"])
def add_player():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    if game_started:
        return redirect(url_for("index"))

    name = (request.form.get("player_name") or "").strip()

    if name != "":
        players.append({
            "name": name,
            "score": 0,
            "miss_count": 0,
            "is_lost": False
        })

    return redirect(url_for("index"))


@app.route("/reset_players", methods=["POST"])
def reset_players():
    global current_player_index, game_started, winner_message

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    players.clear()
    game_history.clear()
    current_player_index = 0
    game_started = False
    winner_message = ""

    return redirect(url_for("index"))


@app.route("/start_game", methods=["POST"])
def start_game():
    global game_started

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    if len(players) < 2:
        return redirect(url_for("index"))

    random.shuffle(players)
    reset_game_status()
    game_started = True

    return redirect(url_for("index"))


@app.route("/submit_score", methods=["POST"])
def submit_score():
    global winner_message

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    if not game_started or winner_message:
        return redirect(url_for("index"))

    current_player = players[current_player_index]

    if current_player["is_lost"]:
        move_to_next_player()
        return redirect(url_for("index"))

    point_text = request.form.get("point", "").strip()

    try:
        point = int(point_text)
    except ValueError:
        return redirect(url_for("index"))

    if point < 0 or point > 12:
        return redirect(url_for("index"))

    save_history()

    update_score(current_player, point)

    if current_player["is_lost"]:
        active_players = get_active_players()

        if len(active_players) == 1:
            winner_message = f'{active_players[0]["name"]}さんの勝利です！'
            return redirect(url_for("index"))

    elif check_winner(current_player):
        winner_message = f'{current_player["name"]}さんの勝利です！'
        return redirect(url_for("index"))

    move_to_next_player()

    while players[current_player_index]["is_lost"]:
        move_to_next_player()

    return redirect(url_for("index"))


@app.route("/undo_score", methods=["POST"])
def undo_score():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    restore_last_history()

    return redirect(url_for("index"))


@app.route("/end_game", methods=["POST"])
def end_game():
    global game_started, winner_message

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    game_started = False
    winner_message = ""
    game_history.clear()

    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)