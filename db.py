import os
import uuid

from dotenv import load_dotenv
from psycopg_pool import ConnectionPool
from psycopg.types.json import Jsonb


load_dotenv(override=True)

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URLが設定されていません。")


pool = ConnectionPool(
    conninfo=DATABASE_URL,
    min_size=1,
    max_size=2,
    timeout=10,
    kwargs={
        "sslmode": "require",
        "connect_timeout": 10
    },
    open=True,
    name="molkky-db-pool"
)


def get_connection():
    return pool.connection()


def create_game():
    game_id = uuid.uuid4()

    initial_state = {
        "players": [],
        "current_player_index": 0,
        "game_started": False,
        "winner_message": ""
    }

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.games (
                    id,
                    state,
                    last_snapshot
                )
                VALUES (%s, %s, %s);
                """,
                (
                    game_id,
                    Jsonb(initial_state),
                    None
                )
            )

    return str(game_id)


def get_game(game_id):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    state,
                    last_snapshot,
                    created_at,
                    updated_at
                FROM public.games
                WHERE id = %s;
                """,
                (game_id,)
            )

            row = cursor.fetchone()

    if row is None:
        return None

    return {
        "id": str(row[0]),
        "state": row[1],
        "last_snapshot": row[2],
        "created_at": row[3],
        "updated_at": row[4]
    }


def save_game(game_id, state, last_snapshot):
    snapshot_value = None

    if last_snapshot is not None:
        snapshot_value = Jsonb(last_snapshot)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.games
                SET
                    state = %s,
                    last_snapshot = %s,
                    updated_at = now()
                WHERE id = %s;
                """,
                (
                    Jsonb(state),
                    snapshot_value,
                    game_id
                )
            )

            if cursor.rowcount == 0:
                raise LookupError(
                    "保存対象のゲームが見つかりません。"
                )


def delete_game(game_id):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM public.games
                WHERE id = %s;
                """,
                (game_id,)
            )

    return True