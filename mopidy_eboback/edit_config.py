from configupdater import ConfigUpdater

class EboBackConfigEditor:
    def __init__(self):
        self.file_name = "/etc/mopidy/mopidy.conf" #todo: make this based on the actual used config file.

    def __enter__(self):
        self.config = ConfigUpdater()
        self.config.read(self.file_name)
        if 'eboback' not in self.config:
            self.config.add_section('eboback')

    def __exit__(self ,exc_type, value, traceback):
        with open(self.file_name, 'w') as file:
            self.config.write(file)

    def add_excluded_file_extension(self, ext: str):
        section = self.config['eboback']
        if 'excluded_file_extensions' in section:
            raw_value = section['excluded_file_extensions'].value or ''
            existing = [ext.strip() for ext in raw_value.replace('\n', ',').split(',') if ext.strip()]
        else:
            existing = []

        if ext.lower() not in [e.lower() for e in existing]:
            existing.append(ext)

        section['excluded_file_extensions'].set_values(existing)
