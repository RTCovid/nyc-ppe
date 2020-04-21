## Data Ingestion Infrastructure
The data that we ingest is grouped into "data files" -- the key concept here is that data from the same file
replaces data uploaded by an earlier version of the file. Its been refactored a few times. I (Russell) will probably refactor it at least one more time to more cleanly support different file formats. The intention, however, is to provide an actual data import layer that is agnostic to the import file format (eg. write the same code to import an object that's an XLSX or a similarly formatted CSV). 

### Concepts
Each mapping contains a few pieces:
```python
class SheetMapping(NamedTuple):
    data_file: DataFile
    sheet_name: Optional[str]  # None for CSV
    mappings: Set[Mapping]
    include_raw: bool
    obj_constructor: Optional[Callable[[Any], 'ImportedRow']] = None
```

Data is converted from CSVs and excel spreadsheets into a series of Python `dict`s. From there, the mappings load
specified keys from these dicts into subclasses of `ImportedRow`. `ImportedRow` subclasses validate the data, and return any database rows that should be generated.

This flow is driven by `xlsx_utils.import_xlsx`. For each row in the sheet, it will:
1. Extract the keys defined by the mapping
2. Call the provided object constructor to create a row object (defined by you)
3. Call `to_objects()` on that row object.
4. Save those objects to the database.


### Format Inference
There is some extremely basic code to guess what type of spreadsheet or CSV we're getting. It lives in `xlsx_utils.guess_mapping`


### Mappers
A mapper is the atom of mapping one cell in the spreadsheet to the structured data passed to your `ImportedRow` subclass.

```python
class Mapping(NamedTuple):
    sheet_column_name: str
    obj_column_name: str
    proc: Optional[Callable[[str, ErrorCollector], Any]] = None
```

Of interest is the `proc` argument, an optional function to map a string to structured data. Many `proc` functions are provided
in `data_mapping.utils`. These functions properly handle collating errors to eventually display in the UI if this is widely used.

