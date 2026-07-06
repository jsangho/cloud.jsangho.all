from dataclasses import asdict, dataclass


@dataclass
class PassengerCommand:
    passenger_id: str
    name: str
    gender: str
    age: str
    sib_sp: str
    parch: str
    survived: str


@dataclass
class BookingCommand:
    pclass: str
    ticket: str
    fare: str
    cabin: str
    embarked: str


@dataclass(frozen=True)
class JamesDirectorQuery:
    id: int
    name: str


@dataclass
class JamesDirectorResponse:
    id: int
    name: str


PersonCommand = PassengerCommand


@dataclass
class TitanicRecordCommand:
    passenger_id: str
    survived: str
    pclass: str
    name: str
    gender: str
    age: str
    sib_sp: str
    parch: str
    ticket: str
    fare: str
    cabin: str
    embarked: str


_RECORD_PREVIEW_FIELDS: tuple[tuple[str, str], ...] = (
    ("passenger_id", "PassengerId"),
    ("survived", "Survived"),
    ("pclass", "Pclass"),
    ("name", "Name"),
    ("gender", "gender"),
    ("age", "Age"),
    ("sib_sp", "SibSp"),
    ("parch", "Parch"),
    ("ticket", "Ticket"),
    ("fare", "Fare"),
    ("cabin", "Cabin"),
    ("embarked", "Embarked"),
)

_PERSON_COMMAND_PREVIEW_FIELDS: tuple[tuple[str, str], ...] = (
    ("passenger_id", "PassengerId"),
    ("survived", "Survived"),
    ("pclass", "Pclass"),
    ("name", "Name"),
    ("gender", "gender"),
    ("age", "Age"),
    ("sib_sp", "SibSp"),
    ("parch", "Parch"),
)

_BOOKING_COMMAND_PREVIEW_FIELDS: tuple[tuple[str, str], ...] = (
    ("pclass", "Pclass"),
    ("ticket", "Ticket"),
    ("fare", "Fare"),
    ("cabin", "Cabin"),
    ("embarked", "Embarked"),
)


def _format_preview_command(
    *, index: int, data: dict[str, object], fields: tuple[tuple[str, str], ...]
) -> str:
    label_width = max(len(label) for _, label in fields)
    lines = [f"── row {index} " + "─" * 40]
    for field, label in fields:
        value = data.get(field, "")
        lines.append(f"  {label:<{label_width}} : {value}")
    return "\n".join(lines)


def format_preview_record(index: int, record: TitanicRecordCommand) -> str:
    return _format_preview_command(
        index=index,
        data=asdict(record),
        fields=_RECORD_PREVIEW_FIELDS,
    )


def format_preview_person_command(index: int, command: PersonCommand) -> str:
    return _format_preview_command(
        index=index,
        data=asdict(command),
        fields=_PERSON_COMMAND_PREVIEW_FIELDS,
    )


def format_preview_booking_command(index: int, command: BookingCommand) -> str:
    return _format_preview_command(
        index=index,
        data=asdict(command),
        fields=_BOOKING_COMMAND_PREVIEW_FIELDS,
    )
