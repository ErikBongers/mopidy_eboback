import pathlib

from mopidy import commands

from mopidy_eboback import storage


class UpdateMetaCommand(commands.Command):
    help = "Update album data based on the metadata of the eboplayer.meta files that are found in the same directory."

    def run(self, args, config):
        library = storage.LocalStorageProvider(config)

        prompt = "Are you sure you want to clear the library? [y/N] "
        media_dir = pathlib.Path(config["eboback"]["media_dir"]).resolve()

        if library.update_meta_data(media_dir):
            print("Meta data updated successfully.")
            return 0

        print("Unable to clear library")
        return 1
