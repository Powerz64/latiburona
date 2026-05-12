from __future__ import annotations

from kivy.properties import BooleanProperty, NumericProperty, ObjectProperty, StringProperty

from kivy_ui.components.cards import CardBox


class ReservationRow(CardBox):
    reservation_id = NumericProperty(0)
    data = ObjectProperty(None, allownone=True)
    show_management_actions = BooleanProperty(True)
    client_name = StringProperty("")
    service_type = StringProperty("")
    datetime_text = StringProperty("")
    people_text = StringProperty("")
    schedule_text = StringProperty("")
    status_text = StringProperty("")
    status_tone = StringProperty("warning")
    promotion_text = StringProperty("")
    discount_text = StringProperty("")
    promo_label_text = StringProperty("")
    match_badge_text = StringProperty("Partido prime")
    total_text = StringProperty("")
    payment_status_text = StringProperty("Pago pendiente")
    payment_tone = StringProperty("warning")
    expiration_text = StringProperty("")
    is_confirmed = BooleanProperty(False)
    on_edit = ObjectProperty(None, allownone=True)
    on_confirm = ObjectProperty(None, allownone=True)
    on_delete = ObjectProperty(None, allownone=True)

    def handle_edit(self) -> None:
        if self.on_edit:
            self.on_edit(self.reservation_id)

    def handle_confirm(self) -> None:
        if self.on_confirm:
            self.on_confirm(self.reservation_id)

    def handle_delete(self) -> None:
        if self.on_delete:
            self.on_delete(self.reservation_id)


class TournamentRow(CardBox):
    tournament_id = NumericProperty(0)
    name_text = StringProperty("")
    category_text = StringProperty("")
    participant_count_text = StringProperty("")
    participants_text = StringProperty("")
    status_text = StringProperty("")
    status_tone = StringProperty("success")
    on_edit = ObjectProperty(None, allownone=True)
    on_delete = ObjectProperty(None, allownone=True)

    def handle_edit(self) -> None:
        if self.on_edit:
            self.on_edit(self.tournament_id)

    def handle_delete(self) -> None:
        if self.on_delete:
            self.on_delete(self.tournament_id)
