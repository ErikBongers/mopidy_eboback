import alsaaudio

# This class only exists to isolate the import of alsaaudio, which gives an error on Windows.
class AlsaProxy:
    def __init__(self, mixer_name: str, card_number: int):
        print("Initializing AlsaProxy")
        print(f"mixer_name: {mixer_name}, card_number: {card_number}")
        self.mixer = alsaaudio.Mixer(mixer_name, cardindex=card_number)

    def setvolume(self, volume_percentage: int):
        self.mixer.setvolume(volume_percentage)
