import alsaaudio

# This class only exists to isolate the import of alsaaudio, which gives an error on Windows.
class AlsaProxy:
    def __init__(self, mixer_name: str):
        self.mixer = alsaaudio.Mixer(mixer_name)

    def setvolume(self, volume_percentage: int):
        self.mixer.setvolume(volume_percentage)
