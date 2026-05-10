from app.models import Tournament
from app.utils.validators import count_participants
from app.utils.validators import ValidationError, validate_tournament_input


class TournamentService:
    def __init__(self, database_service) -> None:
        self.database_service = database_service

    def _row_to_model(self, row) -> Tournament:
        return Tournament(
            id=row["id"],
            name=row["name"],
            category=row["category"],
            participants=row["participants"],
            participant_count=row["participant_count"],
            status=row["status"],
            created_at=row["created_at"],
        )

    def count_tournaments(self) -> int:
        with self.database_service.get_connection() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM tournaments").fetchone()
        return int(row["total"])

    def seed_sample_data_if_empty(self, sample_items: list[dict]) -> None:
        if self.count_tournaments() > 0:
            return
        for item in sample_items:
            self.create_tournament(item)

    def reconcile_existing_records(self) -> None:
        tournaments = self.get_all_tournaments()
        with self.database_service.get_connection() as connection:
            for tournament in tournaments:
                cleaned = validate_tournament_input(
                    {
                        "name": tournament.name,
                        "category": tournament.category,
                        "participants": tournament.participants,
                        "status": tournament.status,
                    }
                )
                connection.execute(
                    """
                    UPDATE tournaments
                    SET participant_count = ?, status = ?
                    WHERE id = ?
                    """,
                    (cleaned["participant_count"], cleaned["status"], tournament.id),
                )

    def get_all_tournaments(self) -> list[Tournament]:
        with self.database_service.get_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM tournaments ORDER BY created_at DESC, name ASC"
            ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def get_tournament(self, tournament_id: int) -> Tournament | None:
        with self.database_service.get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM tournaments WHERE id = ?",
                (tournament_id,),
            ).fetchone()
        return self._row_to_model(row) if row else None

    def create_tournament(self, payload: dict) -> int:
        cleaned = validate_tournament_input(payload)
        with self.database_service.get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO tournaments(name, category, participants, participant_count, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    cleaned["name"],
                    cleaned["category"],
                    cleaned["participants"],
                    cleaned["participant_count"],
                    cleaned["status"],
                ),
            )
        return int(cursor.lastrowid)

    def update_tournament(self, tournament_id: int, payload: dict) -> None:
        if not self.get_tournament(tournament_id):
            raise ValidationError("El torneo seleccionado ya no existe.")
        cleaned = validate_tournament_input(payload)
        with self.database_service.get_connection() as connection:
            connection.execute(
                """
                UPDATE tournaments
                SET name = ?, category = ?, participants = ?, participant_count = ?, status = ?
                WHERE id = ?
                """,
                (
                    cleaned["name"],
                    cleaned["category"],
                    cleaned["participants"],
                    cleaned["participant_count"],
                    cleaned["status"],
                    tournament_id,
                ),
            )

    def delete_tournament(self, tournament_id: int) -> None:
        with self.database_service.get_connection() as connection:
            connection.execute("DELETE FROM tournaments WHERE id = ?", (tournament_id,))

    def get_status_summary(self) -> dict[str, int]:
        with self.database_service.get_connection() as connection:
            rows = connection.execute(
                """
                SELECT status, COUNT(*) AS total
                FROM tournaments
                GROUP BY status
                """
            ).fetchall()
        summary = {"activo": 0, "finalizado": 0}
        for row in rows:
            summary[row["status"]] = int(row["total"])
        return summary

    def get_participant_count(self, participants: str) -> int:
        return count_participants(participants)
