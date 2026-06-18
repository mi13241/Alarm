import datetime
import sys
import os
import threading
import time
import asyncio
import flet as ft
import json
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
import uuid


SOUND_PRESETS = {
    "standard": "Стандартный",
    "urgent": "Срочный",
    "gentle": "Тихий",
    "melody": "Мелодия",
    "system": "Системный",
}

SOUND_LABEL_TO_KEY = {v: k for k, v in SOUND_PRESETS.items()}


def get_sound_label(sound: str) -> str:
    if sound.startswith("file:"):
        return f"📁 {os.path.basename(sound[5:])}"
    return SOUND_PRESETS.get(sound, sound)


@dataclass
class Alarm:
    id: str
    time: datetime.time
    active: bool = True
    triggered: bool = False
    sound: str = "standard"


class AudioPlayer:
    def __init__(self):
        self.current_process = None
        self.lock = threading.Lock()

    def play(self, sound: str = "standard"):
        def play_music():
            try:
                import winsound
                if sound.startswith("file:"):
                    try:
                        from playsound3 import playsound
                        playsound(sound[5:], block=True)
                        return
                    except Exception:
                        pass
                if sound == "urgent":
                    for _ in range(6):
                        winsound.Beep(1400, 150)
                        time.sleep(0.05)
                    for _ in range(3):
                        winsound.Beep(1000, 300)
                        time.sleep(0.1)
                elif sound == "gentle":
                    for _ in range(3):
                        winsound.Beep(600, 800)
                        time.sleep(0.5)
                elif sound == "melody":
                    for freq, dur in [(523, 150), (659, 150), (784, 150),
                                      (1047, 300), (784, 150), (1047, 450)]:
                        winsound.Beep(freq, dur)
                        time.sleep(0.05)
                elif sound == "system":
                    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                    time.sleep(0.8)
                    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                else:
                    for _ in range(3):
                        winsound.Beep(1000, 500)
                        time.sleep(0.2)
            except Exception as e:
                print(f"Ошибка воспроизведения звука: {e}")

        thread = threading.Thread(target=play_music, daemon=True)
        thread.start()
        return thread

    def stop(self):
        pass


class AlarmManager:

    def __init__(self):
        self.alarms: List[Alarm] = []
        self.lock = threading.RLock()
        self.audio_player = AudioPlayer()
        self.current_alarm_thread = None
        self.current_alarm_id = None
        self.cache_file = "alarms_cache.json"
        self.load_alarms_from_cache()

    def save_alarms_to_cache(self):
        with self.lock:
            alarms_data = []
            for alarm in self.alarms:
                alarms_data.append({
                    "id": alarm.id,
                    "hour": alarm.time.hour,
                    "minute": alarm.time.minute,
                    "active": alarm.active,
                    "triggered": alarm.triggered,
                    "sound": alarm.sound,
                })

            try:
                with open(self.cache_file, "w", encoding="utf-8") as f:
                    json.dump(alarms_data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"Ошибка сохранения кэша: {e}")

    def load_alarms_from_cache(self):
        if not os.path.exists(self.cache_file):
            return

        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                alarms_data = json.load(f)

            with self.lock:
                for data in alarms_data:
                    time_obj = datetime.time(hour=data["hour"], minute=data["minute"])
                    alarm = Alarm(
                        id=data["id"],
                        time=time_obj,
                        active=data.get("active", True),
                        triggered=data.get("triggered", False),
                        sound=data.get("sound", "standard"),
                    )
                    self.alarms.append(alarm)
        except Exception as e:
            print(f"Ошибка загрузки кэша: {e}")

    def add_alarm(self, time: datetime.time, sound: str = "standard") -> tuple:
        with self.lock:
            for alarm in self.alarms:
                if alarm.time.hour == time.hour and alarm.time.minute == time.minute:
                    return None, False, "Данный будильник уже существует!"

            alarm = Alarm(id=str(uuid.uuid4())[:8], time=time, active=True, triggered=False, sound=sound)
            self.alarms.append(alarm)
            self.save_alarms_to_cache()
            return alarm, True, ""

    def remove_alarm(self, alarm_id: str) -> bool:
        with self.lock:
            for i, alarm in enumerate(self.alarms):
                if alarm.id == alarm_id:
                    self.alarms.pop(i)
                    self.save_alarms_to_cache()
                    return True
            return False

    def get_all_alarms(self) -> List[Alarm]:
        with self.lock:
            return list(self.alarms)

    def get_active_alarms(self) -> List[Alarm]:
        with self.lock:
            return [a for a in self.alarms if a.active]

    def disable_alarm(self, alarm_id: str):
        with self.lock:
            for alarm in self.alarms:
                if alarm.id == alarm_id:
                    alarm.active = False
                    self.save_alarms_to_cache()
                    break

    def enable_alarm(self, alarm_id: str):
        with self.lock:
            for alarm in self.alarms:
                if alarm.id == alarm_id:
                    alarm.active = True
                    self.save_alarms_to_cache()
                    break

    def mark_as_triggered(self, alarm_id: str):
        with self.lock:
            for alarm in self.alarms:
                if alarm.id == alarm_id:
                    alarm.triggered = True
                    alarm.active = False
                    break

    def play_alarm_sound(self, sound: str = "standard"):
        self.current_alarm_thread = self.audio_player.play(sound)

    def check_alarms(self, now: datetime.datetime) -> List[Alarm]:
        triggered = []
        with self.lock:
            for alarm in self.alarms:
                if alarm.active and alarm.time.hour == now.hour and alarm.time.minute == now.minute:
                    triggered.append(alarm)
                    # Отключаем будильник после срабатывания, но не помечаем как triggered,
                    # чтобы пользователь мог включить его снова на следующий день.
                    alarm.active = False
        return triggered


async def main(page: ft.Page):
    page.title = "Будильник"
    page.bgcolor = "#0B0C10"
    page.theme_mode = "dark"
    page.scroll = ft.ScrollMode.ALWAYS

    alarm_manager = AlarmManager()
    running = [True]

    time_display = ft.Text(
        value=datetime.datetime.now().strftime("%H:%M:%S"),
        size=60,
        weight=ft.FontWeight.BOLD,
        color="#E94560",
        text_align=ft.TextAlign.CENTER,
    )

    hour_dropdown = ft.Dropdown(
        label="Часы",
        width=100,
        options=[ft.dropdown.Option(f"{h:02d}") for h in range(24)],
        value="07",
        bgcolor="#16213E",
        color="white",
        border_color="#E94560",
    )

    minute_dropdown = ft.Dropdown(
        label="Минуты",
        width=100,
        options=[ft.dropdown.Option(f"{m:02d}") for m in range(60)],
        value="00",
        bgcolor="#16213E",
        color="white",
        border_color="#E94560",
    )

    status_text = ft.Text(
        value="Будильники не установлены",
        color="#AAAAAA",
        size=14,
        text_align=ft.TextAlign.CENTER,
    )

    alarms_list = ft.Column(
        controls=[],
        spacing=10,
        height=300,
        scroll=ft.ScrollMode.AUTO,
    )

    alarms_count_text = ft.Text(
        value="Активных будильников: 0",
        color="#4CC9F0",
        size=12,
        text_align=ft.TextAlign.CENTER,
    )

    alarms_container = ft.Container(
        content=alarms_list,
        border=ft.Border.all(1, "#16213E"),
        border_radius=10,
        padding=10,
        visible=False,
    )

    sound_dropdown = ft.Dropdown(
        label="Звук будильника",
        width=200,
        options=[ft.dropdown.Option(label) for label in SOUND_PRESETS.values()],
        value="Стандартный",
        bgcolor="#16213E",
        color="white",
        border_color="#E94560",
    )

    alarm_cards: Dict[str, dict] = {}

    async def close_dialog(e):
        alarm_dialog.open = False
        page.update()

    alarm_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("⏰ БУДИЛЬНИК!"),
        content=ft.Text("Пора вставать!", size=20),
        actions=[ft.TextButton("Выключить", on_click=close_dialog)],
    )
    page.overlay.append(alarm_dialog)

    async def update_alarms_list():
        all_alarms = alarm_manager.get_all_alarms()
        active_alarms = alarm_manager.get_active_alarms()

        alarms_count_text.value = f"Активных будильников: {len(active_alarms)}"

        updated_ids = set()
        for alarm in all_alarms:
            alarm_time_str = alarm.time.strftime("%H:%M")
            alarm_id = alarm.id
            updated_ids.add(alarm_id)

            is_triggered = alarm.triggered
            is_active = alarm.active and not is_triggered

            if alarm_id not in alarm_cards:
                async def on_switch_change(e, aid=alarm_id):
                    if e.control.value:
                        alarm_manager.enable_alarm(aid)
                    else:
                        alarm_manager.disable_alarm(aid)
                    await update_alarms_list()

                async def on_delete_click(e, aid=alarm_id):
                    alarm_manager.remove_alarm(aid)
                    await update_alarms_list()

                switch = ft.Switch(
                    value=is_active,
                    active_color="#E94560",
                    on_change=on_switch_change,
                )

                delete_btn = ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    icon_color="#E94560",
                    on_click=on_delete_click,
                    tooltip="Удалить будильник",
                )

                status_text_elem = ft.Text(
                    value="Активен" if is_active else ("Сработал" if is_triggered else "Выключен"),
                    color="#4CC9F0" if is_active else ("#E94560" if is_triggered else "#AAAAAA"),
                    size=12,
                )

                sound_label_elem = ft.Text(
                    value=get_sound_label(alarm.sound),
                    color="#666666",
                    size=11,
                )

                card = ft.Card(
                    content=ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Column(
                                    controls=[
                                        ft.Text(
                                            value=f"⏰ {alarm_time_str}",
                                            color="#FFFFFF",
                                            size=16,
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                        status_text_elem,
                                        sound_label_elem,
                                    ],
                                    spacing=2,
                                    alignment=ft.MainAxisAlignment.CENTER,
                                ),
                                ft.Container(expand=True),
                                ft.Row(
                                    controls=[
                                        switch,
                                        ft.Container(width=10),
                                        delete_btn,
                                    ],
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=ft.Padding(left=15, top=10, right=15, bottom=10),
                    ),
                    bgcolor="#16213E" if is_active else ("#2C3E50" if is_triggered else "#34495E"),
                    shape=ft.RoundedRectangleBorder(radius=10),
                    elevation=2,
                )

                alarm_cards[alarm_id] = {
                    "card": card,
                    "switch": switch,
                    "status": status_text_elem,
                }
                alarms_list.controls.append(card)
            else:
                card_info = alarm_cards[alarm_id]
                card = card_info["card"]
                status_text_elem = card_info["status"]
                switch = card_info["switch"]

                card.content.content.controls[0].controls[0].value = f"⏰ {alarm_time_str}"
                status_text_elem.value = "Сработал" if is_triggered else ("Активен" if is_active else "Выключен")
                status_text_elem.color = "#E94560" if is_triggered else ("#4CC9F0" if is_active else "#AAAAAA")
                card.bgcolor = "#2C3E50" if is_triggered else ("#16213E" if is_active else "#34495E")
                switch.value = is_active

        for aid in list(alarm_cards.keys()):
            if aid not in updated_ids:
                old_card = alarm_cards[aid]["card"]
                if old_card in alarms_list.controls:
                    alarms_list.controls.remove(old_card)
                del alarm_cards[aid]

        alarms_container.visible = len(all_alarms) > 0
        page.update()

    async def add_alarm(e):
        try:
            h = int(hour_dropdown.value)
            m = int(minute_dropdown.value)
        except (TypeError, ValueError):
            status_text.value = "Некорректное время"
            status_text.color = "#E94560"
            page.update()
            return

        now = datetime.datetime.now()
        candidate = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if candidate <= now:
            candidate += datetime.timedelta(days=1)

        sound = SOUND_LABEL_TO_KEY.get(sound_dropdown.value, "standard")
        alarm, success, message = alarm_manager.add_alarm(candidate.time(), sound)

        if success:
            status_text.value = f"Будильник установлен на {candidate.strftime('%H:%M')}"
            status_text.color = "#4CC9F0"
        else:
            status_text.value = message
            status_text.color = "#E94560"

        await update_alarms_list()

    async def background_clock():
        last_trigger_check = None
        while running[0]:
            now = datetime.datetime.now()
            time_display.value = now.strftime("%H:%M:%S")

            triggered = alarm_manager.check_alarms(now)
            if triggered:
                current_minute = (now.hour, now.minute)
                if current_minute != last_trigger_check:
                    last_trigger_check = current_minute
                    status_text.value = f"БУДИЛЬНИК! 🚨"
                    status_text.color = "#E94560"
                    status_text.weight = ft.FontWeight.BOLD
                    alarm_manager.play_alarm_sound(triggered[0].sound)
                    alarm_dialog.open = True
                    await update_alarms_list()

            page.update()
            await asyncio.sleep(0.5)

    def on_close(e):
        running[0] = False
        alarm_manager.save_alarms_to_cache()

    add_btn = ft.FilledButton(
        "Добавить будильник",
        icon=ft.Icons.ALARM_ADD,
        style=ft.ButtonStyle(bgcolor="#E94560", color="white"),
        on_click=add_alarm,
    )

    page.on_close = on_close

    page.add(
        ft.Column(
            [
                ft.Container(height=20),
                time_display,
                ft.Container(height=20),
                ft.Row(
                    controls=[hour_dropdown, minute_dropdown],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                ft.Container(height=10),
                ft.Row(
                    controls=[sound_dropdown],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                ft.Row(
                    controls=[add_btn],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                ft.Container(height=10),
                status_text,
                ft.Container(height=10),
                alarms_count_text,
                ft.Container(height=10),
                alarms_container,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=15,
        )
    )

    await update_alarms_list()

    page.run_task(background_clock)


if __name__ == "__main__":
    ft.run(main)