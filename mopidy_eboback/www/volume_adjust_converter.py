import logging
from typing import cast

logger = logging.getLogger(__name__)

class VolumeAdjustConverter:
    def __init__(self, config_volume_adjustments):
        self.volume_adjustments: dict[int, int]  = self.build_volume_adjustments(config_volume_adjustments)

    def to_percentage(self, volume_adjust: int | None):
        if volume_adjust is None:
            return self.volume_adjustments[0]
        #todo: check if volume_adjust is out of bounds.
        return self.volume_adjustments[volume_adjust]

    default_volume_adjustments: dict[int, int] = {
        -5: 20,
        -4: 25,
        -3: 30,
        -2: 35,
        -1: 40,
        0: 50,
        1: 60,
        2: 70,
        3: 80,
        4: 90,
        5: 100,
    }

    @staticmethod
    def build_volume_adjustments(config_volume_adjust: list[str]) -> dict[int, int]:
        if len(config_volume_adjust) != 11:
            logger.error(f"volume_adjust needs 11 values. Found {len(config_volume_adjust)}")
            return VolumeAdjustConverter.default_volume_adjustments

        if not all(x.startswith("level") and x.endswith("%") for x in config_volume_adjust):
            logger.error(
                f"volume_adjust levels not formatted properly. Needs to be level<lvl> = <percentage>%, where lvl in [-5..5]")
            return VolumeAdjustConverter.default_volume_adjustments

        stripped = [x[5:-1] for x in config_volume_adjust]
        splitted = [x.split("=") for x in stripped]
        numbers = [[int(y.strip()) for y in x] for x in splitted]
        if not all([len(x) == 2 for x in numbers]):
            logger.error(
                f"volume_adjust needs 2 values per row. Found {numbers} Needs to be level<lvl> = <percentage>%, where lvl in [-5..5]")
            return VolumeAdjustConverter.default_volume_adjustments

        volume_adjustments = {row[0]: row[1] for row in numbers}
        return volume_adjustments