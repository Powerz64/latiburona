from __future__ import annotations

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup

from kivy_ui.components.buttons import DangerButton, PrimaryButton, SecondaryButton, SuccessButton
from kivy_ui.theme import UI_FONT, active_theme_hex, rgba


class MessageDialog(Popup):
    def __init__(self, title_text: str, message_text: str, tone: str = "primary", **kwargs) -> None:
        theme = active_theme_hex()
        separator = theme.get(tone, theme["primary"])
        super().__init__(
            title=title_text,
            title_align="left",
            title_font=UI_FONT,
            title_color=rgba(theme["text_primary"]),
            separator_color=rgba(separator),
            size_hint=(None, None),
            size=(dp(540), dp(280)),
            auto_dismiss=False,
            **kwargs,
        )
        self.background_color = rgba(theme["surface"])
        content = BoxLayout(orientation="vertical", padding=dp(22), spacing=dp(18))
        content.add_widget(
            Label(
                text=message_text,
                font_name=UI_FONT,
                color=rgba(theme["text_secondary"]),
                halign="left",
                valign="middle",
                text_size=(dp(468), None),
            )
        )
        close_button = PrimaryButton(text="Cerrar", size_hint_y=None, height=dp(46))
        close_button.bind(on_release=lambda *_args: self.dismiss())
        content.add_widget(close_button)
        self.content = content


class ConfirmDialog(Popup):
    def __init__(
        self,
        title_text: str,
        message_text: str,
        on_confirm,
        *,
        tone: str = "warning",
        confirm_text: str = "Confirmar",
        **kwargs,
    ) -> None:
        theme = active_theme_hex()
        confirm_button_cls = {
            "success": SuccessButton,
            "danger": DangerButton,
        }.get(tone, PrimaryButton)
        super().__init__(
            title=title_text,
            title_align="left",
            title_font=UI_FONT,
            title_color=rgba(theme["text_primary"]),
            separator_color=rgba(theme.get(tone, theme["warning"])),
            size_hint=(None, None),
            size=(dp(560), dp(300)),
            auto_dismiss=False,
            **kwargs,
        )
        self.background_color = rgba(theme["surface"])
        content = BoxLayout(orientation="vertical", padding=dp(22), spacing=dp(18))
        content.add_widget(
            Label(
                text=message_text,
                font_name=UI_FONT,
                color=rgba(theme["text_secondary"]),
                halign="left",
                valign="middle",
                text_size=(dp(488), None),
            )
        )

        actions = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(12))
        cancel_button = SecondaryButton(text="Cancelar")
        confirm_button = confirm_button_cls(text=confirm_text)
        cancel_button.bind(on_release=lambda *_args: self.dismiss())
        confirm_button.bind(on_release=lambda *_args: self._handle_confirm(on_confirm))
        actions.add_widget(cancel_button)
        actions.add_widget(confirm_button)
        content.add_widget(actions)
        self.content = content

    def _handle_confirm(self, callback) -> None:
        self.dismiss()
        if callback:
            callback()


def show_message(title_text: str, message_text: str, tone: str = "primary") -> None:
    MessageDialog(title_text, message_text, tone=tone).open()


def ask_confirmation(
    title_text: str,
    message_text: str,
    on_confirm,
    *,
    tone: str = "warning",
    confirm_text: str = "Confirmar",
) -> None:
    ConfirmDialog(
        title_text,
        message_text,
        on_confirm,
        tone=tone,
        confirm_text=confirm_text,
    ).open()
