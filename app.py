from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "temporary-secret-key"

APP_PASSWORD = "molkky"

players = []
current_player_index = 0
game_started = False
winner_message = ""


def reset_game_status():
    global current_player_index, game_started, winner_message

    current_player_index = 0
    game_started = False
    winner_message = ""

    for player in players:
        player["score"] = 0
        player["miss_count"] = 0
        player["is_lost"] = False


def get_active_players():
    active_players = []

    for player in players:
        if not player["is_lost"]:
            active_players.append(player)

    return active_players


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

    if game_started and len(players) > 0 and not winner_message:
        current_player = players[current_player_index]

    return render_template(
        "index.html",
        players=players,
        game_started=game_started,
        current_player=current_player,
        winner_message=winner_message
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

    name = request.form.get("player_name").strip()

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


@app.route("/end_game", methods=["POST"])
def end_game():
    global game_started, winner_message

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    game_started = False
    winner_message = ""

    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)