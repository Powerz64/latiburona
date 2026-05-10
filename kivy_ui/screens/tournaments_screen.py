from __future__ import annotations

from kivy.app import App
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty

from app.utils.constants import TOURNAMENT_CATEGORIES, TOURNAMENT_STATUS_OPTIONS
from app.utils.formatters import format_date
from app.utils.validators import ValidationError
from kivy_ui.components.rows import TournamentRow
from kivy_ui.screens.base_screen import ServiceScreen


class TournamentsScreen(ServiceScreen):
    category_options = ListProperty(TOURNAMENT_CATEGORIES)
    status_options = ListProperty([status.title() for status in TOURNAMENT_STATUS_OPTIONS])
    participant_count_text = StringProperty("Participantes detectados: 0")
    summary_text = StringProperty("Sin torneos registrados.")
    form_heading = StringProperty("Nuevo torneo")
    save_button_text = StringProperty("Guardar torneo")
    current_tournament_id = NumericProperty(0)
    has_tournaments = BooleanProperty(False)
    tournaments_data = ListProperty([])

    def on_kv_post(self, *_args) -> None:
        self.bind(size=self._update_layout)
        self.ids.participants_input.bind(text=lambda *_args: self.update_participant_preview())
        self._update_layout()

    def _update_layout(self, *_args) -> None:
        if not self.ids:
            return
        self.ids.content_grid.cols = 1 if self.width < dp(1200) else 2

    def refresh(self) -> None:
        self.set_status("Cargando torneos...")
        self.load_data(
            "tournaments_refresh",
            self._fetch_tournaments_data,
            self._apply_tournaments_data,
            self._handle_tournaments_error,
            loading_message="Cargando torneos...",
            show_loading_overlay=False,
        )

    def _fetch_tournaments_data(self) -> dict:
        tournaments = self.get_service("tournament_service").get_all_tournaments()
        summary = self.get_service("tournament_service").get_status_summary()
        return {
            "has_tournaments": bool(tournaments),
            "summary_text": (
                f"Activos: {summary['activo']} | Finalizados: {summary['finalizado']} | Total: {len(tournaments)}"
            ),
            "tournaments_data": [
                {
                    "tournament_id": tournament.id or 0,
                    "name_text": tournament.name,
                    "category_text": f"{tournament.category} | Creado {format_date((tournament.created_at or '')[:10])}",
                    "participant_count_text": self._participant_count_text(tournament.participants),
                    "participants_text": self._participants_preview_text(tournament.participants),
                    "status_text": tournament.status.title(),
                    "status_tone": "success" if tournament.status == "activo" else "warning",
                    "on_edit": self.load_tournament,
                    "on_delete": self.request_delete_tournament,
                }
                for tournament in tournaments
            ],
        }

    def _apply_tournaments_data(self, payload: dict) -> None:
        self.has_tournaments = payload["has_tournaments"]
        self.summary_text = payload["summary_text"]
        self.tournaments_data = payload["tournaments_data"]
        self._render_tournaments()
        self.update_participant_preview()
        self.set_status("Torneos sincronizados con el panel operativo.")

    def _handle_tournaments_error(self, error: Exception) -> None:
        self.has_tournaments = bool(self.tournaments_data)
        self.summary_text = "No fue posible cargar los torneos."
        self._render_tournaments()
        self.set_status(f"Error al cargar torneos: {error}")

    def _render_tournaments(self) -> None:
        if not self.ids or "tournaments_list" not in self.ids:
            return
        container = self.ids.tournaments_list
        container.clear_widgets()
        for item in self.tournaments_data:
            container.add_widget(TournamentRow(**item))

    def _participants_list(self, participants) -> list[str]:
        if isinstance(participants, str):
            rows = [row.strip() for row in participants.splitlines() if row.strip()]
            if not rows:
                rows = [chunk.strip() for chunk in participants.split(",") if chunk.strip()]
            elif any("," in row for row in rows):
                expanded: list[str] = []
                for row in rows:
                    expanded.extend(chunk.strip() for chunk in row.split(",") if chunk.strip())
                rows = expanded
            return rows
        if isinstance(participants, (list, tuple, set)):
            return [str(item).strip() for item in participants if str(item).strip()]
        return []

    def _participant_count_text(self, participants) -> str:
        participant_list = self._participants_list(participants)
        total = len(participant_list)
        return f"{total} participante{'s' if total != 1 else ''}"

    def _participants_preview_text(self, participants) -> str:
        participant_list = self._participants_list(participants)
        if not participant_list:
            return "Sin participantes registrados."
        visible = ", ".join(participant_list[:4])
        if len(participant_list) > 4:
            return f"{visible} +{len(participant_list) - 4} más"
        return visible

    def update_participant_preview(self) -> None:
        participants = self.ids.participants_input.text.strip()
        count = len(self._participants_list(participants))
        self.participant_count_text = f"Participantes detectados: {count}"

    def save_tournament(self) -> None:
        payload = {
            "name": self.ids.name_input.text,
            "category": self.ids.category_spinner.text,
            "participants": self.ids.participants_input.text,
            "status": self.ids.status_spinner.text.lower(),
        }
        self.set_status("Guardando torneo...")
        self.run_in_background(
            "tournament_save",
            lambda: self._perform_save(payload),
            self._handle_save_success,
            self._handle_save_error,
        )

    def _perform_save(self, payload: dict) -> dict:
        tournament_service = self.get_service("tournament_service")
        if self.current_tournament_id:
            tournament_service.update_tournament(self.current_tournament_id, payload)
            return {"title": "Torneo actualizado", "message": "El torneo fue actualizado correctamente."}
        tournament_service.create_tournament(payload)
        return {"title": "Torneo creado", "message": "El torneo fue registrado correctamente."}

    def _handle_save_success(self, payload: dict) -> None:
        self.notify(payload["title"], payload["message"], tone="success")
        self.clear_form()
        App.get_running_app().refresh_screens(["tournaments"])

    def _handle_save_error(self, error: Exception) -> None:
        if isinstance(error, ValidationError):
            self.notify("Validacion", str(error), tone="warning")
            return
        self.notify("Torneo", "No fue posible guardar el torneo.", tone="danger")
        self.set_status(f"Error al guardar torneo: {error}")

    def clear_form(self) -> None:
        self.current_tournament_id = 0
        self.form_heading = "Nuevo torneo"
        self.save_button_text = "Guardar torneo"
        self.ids.name_input.text = ""
        self.ids.category_spinner.text = self.category_options[0]
        self.ids.status_spinner.text = self.status_options[0]
        self.ids.participants_input.text = ""
        self.participant_count_text = "Participantes detectados: 0"
        self.set_status("Formulario de torneo listo para una nueva carga.")

    def load_tournament(self, tournament_id: int) -> None:
        self.set_status("Cargando torneo...")
        self.run_in_background(
            "tournament_load",
            lambda: self.get_service("tournament_service").get_tournament(tournament_id),
            self._apply_loaded_tournament,
            self._handle_load_tournament_error,
        )

    def _apply_loaded_tournament(self, tournament) -> None:
        if tournament is None:
            self.notify("Torneo", "No se encontro el torneo seleccionado.", tone="danger")
            App.get_running_app().refresh_screens(["tournaments"])
            return

        self.current_tournament_id = tournament.id or 0
        self.form_heading = f"Editando torneo #{tournament.id}"
        self.save_button_text = "Actualizar torneo"
        self.ids.name_input.text = tournament.name
        self.ids.category_spinner.text = tournament.category
        self.ids.status_spinner.text = tournament.status.title()
        self.ids.participants_input.text = "\n".join(self._participants_list(tournament.participants))
        self.update_participant_preview()
        self.set_status(f"Torneo #{tournament.id} cargado en el formulario.")

    def _handle_load_tournament_error(self, error: Exception) -> None:
        self.notify("Torneo", "No fue posible cargar el torneo seleccionado.", tone="danger")
        self.set_status(f"Error al cargar torneo: {error}")

    def request_delete_tournament(self, tournament_id: int) -> None:
        self.confirm_action(
            "Eliminar torneo",
            "Esta accion eliminara el torneo seleccionado. Confirma para continuar.",
            lambda: self._delete_tournament(tournament_id),
        )

    def _delete_tournament(self, tournament_id: int) -> None:
        self.set_status("Eliminando torneo...")
        self.run_in_background(
            "tournament_delete",
            lambda: self._perform_delete(tournament_id),
            lambda _payload: self._handle_delete_success(tournament_id),
            self._handle_delete_error,
        )

    def _perform_delete(self, tournament_id: int) -> dict:
        self.get_service("tournament_service").delete_tournament(tournament_id)
        return {"tournament_id": tournament_id}

    def _handle_delete_success(self, tournament_id: int) -> None:
        if self.current_tournament_id == tournament_id:
            self.clear_form()
        self.notify("Torneo eliminado", "El torneo fue eliminado correctamente.", tone="danger")
        App.get_running_app().refresh_screens(["tournaments"])

    def _handle_delete_error(self, error: Exception) -> None:
        self.notify("Torneo", "No fue posible eliminar el torneo.", tone="danger")
        self.set_status(f"Error al eliminar torneo: {error}")
