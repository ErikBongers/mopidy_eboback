from mopidy_eboback import storage


class ClearCommand:
    help = "Clear local media files from the eboplayer library."
    def __init__(self):
        pass

    # noinspection method-may-be-static
    def run(self, config):
        library = storage.LocalStorageProvider(config)

        prompt = "Are you sure you want to clear the library? [y/N] "

        if input(prompt).lower() != "y":
            print("Clearing library aborted")
            return 0

        if library.clear_except_history():
            print("Library successfully cleared")
            return 0

        print("Unable to clear library")
        return 1
