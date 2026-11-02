import logging
import os

import alsaaudio

logger = logging.getLogger(__name__)
IS_WSL = "microsoft" in os.uname().release.lower()

# This class only exists to isolate the import of alsaaudio, which gives an error on Windows.
class AlsaProxy:
    def __init__(self, mixer_name: str, card_number: int):
        if not IS_WSL:
            logger.info(f"mixer_name: {mixer_name}, card_number: {card_number}")
            self.mixer = alsaaudio.Mixer(mixer_name, cardindex=card_number)
        else:
            self.mixer = None
            print("Running on WSL2: Hardware mixer controls bypassed.")

    def setvolume(self, volume_percentage: int):
        logger.info(f"Setting volume to {volume_percentage}%")
        if self.mixer:
            self.mixer.setvolume(volume_percentage)
