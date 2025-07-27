import os
import pygame

class MusicManager:
    def __init__(self, music_folder):
        self.current_track = None
        self.music_folder = music_folder
        self.track_list = [f for f in os.listdir(music_folder) if f.lower().endswith(('.mp3', '.ogg', '.wav'))]
        self.tracks = [
            os.path.join(music_folder, f)
            for f in os.listdir(music_folder)
            if f.lower().endswith((".mp3", ".ogg", ".wav"))
        ]
        self.current_index = 0
        pygame.mixer.music.set_endevent(pygame.USEREVENT + 1)  # Track end event

    def play_current(self):
        if not self.tracks:
            print("[MUSIC] No music files found.")
            return

        try:
            self.current_track = self.tracks[self.current_index]
            pygame.mixer.music.load(self.tracks[self.current_index])
            pygame.mixer.music.play(loops=-1)  # ← Loop forever
            print(f"[MUSIC] Now playing: {self.tracks[self.current_index]}")
        except Exception as e:
            print(f"[MUSIC ERROR] Could not play music: {e}")

    def next_track(self):
        self.current_index = (self.current_index + 1) % len(self.tracks)
        self.play_current()

    def previous_track(self):
        self.current_index = (self.current_index - 1) % len(self.tracks)
        self.play_current()

    def set_volume(self, volume):
        pygame.mixer.music.set_volume(volume)  # 0.0 to 1.0

    def handle_event(self, event):
        if event.type == pygame.USEREVENT + 1:
            self.next_track()  # Auto-play next when current ends

    def get_current_track_name(self):
        if self.track_list:
            return self.track_list[self.current_index]
        return "No Track"
