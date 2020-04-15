class DataImportError(Exception):
    pass


class NoMappingForFileError(DataImportError):
    pass


class PartialFile(DataImportError):
    pass


class ImportInProgressError(DataImportError):
    def __init__(self, import_id):
        self.import_id = import_id


class CsvImportError(DataImportError):
    pass