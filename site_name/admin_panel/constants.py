from datetime import datetime


TYPE_STR = 1
TYPE_INT = 2
TYPE_FLOAT = 3
TYPE_DATE = 4
TYPE_DATETIME = 5

VALUES_TYPE_MAPPING = {
    TYPE_STR: str,
    TYPE_INT: int,
    TYPE_FLOAT: float,
    TYPE_DATE: datetime,
    TYPE_DATETIME: datetime
}


SETTING_VALUE_TYPES = (
    (TYPE_STR, "Text"),
    (TYPE_INT, "Integer number"),
    (TYPE_FLOAT, "Float point number"),
    (TYPE_DATE, "Date: YYYY-MM-DD"),
    (TYPE_DATETIME, "Datetime: YYYY-MM-DD HH:MM:SS")
)

WHITE_LIST_PATTERN_TYPE_CHOICE = (
    ('domain', 'Domain'),
    ('full', 'Full'),
)
