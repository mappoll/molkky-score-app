import copy
import os
import random

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for

from db import create_game, delete_game, delete_old_games, get_game, save_game


load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")

APP_PASSWORD = os.environ.get("APP_PASSWORD")

if not app.secret_key:
    raise RuntimeError("SECRET_KEYが設定されていません。")

if not APP_PASSWORD:
    raise RuntimeError("APP_PASSWORDが設定されていません。")


def create_player(name):
    return {
        "name": name,
        "score": 0,
        "miss_count": 0,
        "is_lost": False,
        "last_point": None
    }


def create_initial_state(player_names=None):
    players = []

    if player_names:
        for name in player_names:
            players.append(create_player(name))

    return {
        "players": players,
        "current_player_index": 0,
        "game_started": False,
        "winner_message": ""
    }


def get_current_game():
    delete_old_games()

    game_id = session.get("game_id")

    if game_id:
        game = get_game(game_id)

        if game is not None:
            return game

    game_id = create_game()
    session["game_id"] = game_id

    game = get_game(game_id)

    if game is None:
        raise RuntimeError("作成したゲームを読み込めませんでした。")

    return game


def reset_game_status(state):
    state["current_player_index"] = 0
    state["game_started"] = False
    state["winner_message"] = ""

    for player in state["players"]:
        player["score"] = 0
        player["miss_count"] = 0
        player["is_lost"] = False
        player["last_point"] = None


def get_active_players(state):
    active_players = []

    for player in state["players"]:
        if not player["is_lost"]:
            active_players.append(player)

    return active_players


def get_ranking(state):
    return sorted(
        state["players"],
        key=lambda player: (
            player["is_lost"],
            -player["score"],
            player["miss_count"]
        )
    )
    
def render_game_page(game):
    state = game["state"]

    players = state["players"]
    game_started = state["game_started"]
    winner_message = state["winner_message"]
    current_player_index = state["current_player_index"]

    current_player = None
    ranking = []

    if game_started and players and not winner_message:
        if current_player_index >= len(players):
            current_player_index = 0
            state["current_player_index"] = 0

            save_game(
                game["id"],
                state,
                game["last_snapshot"]
            )

        current_player = players[current_player_index]

    if winner_message:
        ranking = get_ranking(state)

    return render_template(
        "index.html",
        players=players,
        game_started=game_started,
        current_player=current_player,
        current_player_index=current_player_index,
        winner_message=winner_message,
        ranking=ranking,
        can_undo=game["last_snapshot"] is not None
    )


def update_score(player, point):
    player["last_point"] = point

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


def move_to_next_player(state):
    players = state["players"]

    if len(players) == 0:
        return

    state["current_player_index"] = (
        state["current_player_index"] + 1
    ) % len(players)


@app.route("/")
def index():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    game = get_current_game()

    return render_game_page(game)


@app.route("/login", methods=["GET", "POST"])
def login():
    error_message = ""

    if request.method == "POST":
        password = request.form.get("password")

        if password == APP_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))

        error_message = "パスワードが違います。"

    return render_template(
        "login.html",
        error_message=error_message
    )


@app.route("/add_player", methods=["POST"])
def add_player():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    game = get_current_game()
    state = game["state"]

    if state["game_started"]:
        return redirect(url_for("index"))

    name = (request.form.get("player_name") or "").strip()

    if name:
        state["players"].append(create_player(name))

        save_game(
            game["id"],
            state,
            None
        )

    return redirect(url_for("index"))


@app.route(
    "/delete_player/<int:player_index>",
    methods=["POST"]
)
def delete_player(player_index):
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    game = get_current_game()
    state = game["state"]

    if state["game_started"]:
        return redirect(url_for("index"))

    players = state["players"]

    if 0 <= player_index < len(players):
        players.pop(player_index)
        state["current_player_index"] = 0

        save_game(
            game["id"],
            state,
            None
        )

    return redirect(url_for("index"))


@app.route("/reset_players", methods=["POST"])
def reset_players():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    game = get_current_game()
    state = create_initial_state()

    save_game(
        game["id"],
        state,
        None
    )

    return redirect(url_for("index"))


@app.route("/start_game", methods=["POST"])
def start_game():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    game = get_current_game()
    state = game["state"]

    if state["game_started"]:
        return redirect(url_for("index"))

    submitted_names = request.form.getlist("player_names")

    if submitted_names:
        players = []

        for name in submitted_names:
            clean_name = name.strip()

            if clean_name:
                players.append(create_player(clean_name))

        state["players"] = players

    if len(state["players"]) < 2:
        flash("参加者は2名以上入力してください。")
        return redirect(url_for("index"))

    reset_game_status(state)
    random.shuffle(state["players"])
    state["game_started"] = True

    save_game(
        game["id"],
        state,
        None
    )

    return redirect(url_for("index"))


@app.route("/submit_score", methods=["POST"])
def submit_score():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    game = get_current_game()
    state = game["state"]

    if (
        not state["game_started"]
        or state["winner_message"]
    ):
        return redirect(url_for("index"))

    players = state["players"]

    if not players:
        return redirect(url_for("index"))

    current_player_index = state["current_player_index"]
    current_player = players[current_player_index]

    if current_player["is_lost"]:
        return redirect(url_for("index"))

    point_text = request.form.get("point", "").strip()

    try:
        point = int(point_text)
    except ValueError:
        return redirect(url_for("index"))

    if point < 0 or point > 12:
        return redirect(url_for("index"))

    last_snapshot = copy.deepcopy(state)

    update_score(current_player, point)

    if current_player["is_lost"]:
        active_players = get_active_players(state)

        if len(active_players) == 1:
            state["winner_message"] = (
                f'{active_players[0]["name"]}さんの勝利です！'
            )

    elif check_winner(current_player):
        state["winner_message"] = (
            f'{current_player["name"]}さんの勝利です！'
        )

    if not state["winner_message"]:
        move_to_next_player(state)

        while players[state["current_player_index"]]["is_lost"]:
            move_to_next_player(state)

    save_game(
        game["id"],
        state,
        last_snapshot
    )

    game["state"] = state
    game["last_snapshot"] = last_snapshot

    return render_game_page(game)

@app.route("/undo_score", methods=["POST"])
def undo_score():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    game = get_current_game()
    last_snapshot = game["last_snapshot"]

    if last_snapshot is None:
        return redirect(url_for("index"))

    save_game(
        game["id"],
        last_snapshot,
        None
    )

    game["state"] = last_snapshot
    game["last_snapshot"] = None

    return render_game_page(game)

@app.route("/end_game", methods=["POST"])
def end_game():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    game = get_current_game()
    state = game["state"]

    player_names = []

    for player in state["players"]:
        player_names.append(player["name"])

    delete_game(game["id"])

    new_game_id = create_game()
    session["game_id"] = new_game_id

    new_state = create_initial_state(player_names)

    save_game(
        new_game_id,
        new_state,
        None
    )

    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    game_id = session.get("game_id")

    if game_id:
        delete_game(game_id)

    session.clear()

    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)