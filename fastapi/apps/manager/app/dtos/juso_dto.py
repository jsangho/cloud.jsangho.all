from dataclasses import dataclass


@dataclass(frozen=True)
class JusoQuery:
    id: int
    name: str


@dataclass
class JusoResponse:
    id: int
    name: str
    description: str


@dataclass
class ContactListItem:
    id: int
    name: str
    email: str
    phone: str
    org_name: str


@dataclass
class ContactRecordCommand:
    name: str
    given_name: str
    family_name: str
    nickname: str
    birthday: str
    gender: str
    occupation: str
    notes: str
    group_membership: str
    email_1_type: str
    email_1_value: str
    email_2_type: str
    email_2_value: str
    phone_1_type: str
    phone_1_value: str
    phone_2_type: str
    phone_2_value: str
    address_1_formatted: str
    address_1_street: str
    address_1_city: str
    address_1_region: str
    address_1_postal_code: str
    address_1_country: str
    org_name: str
    org_title: str
    org_department: str
    website_1_value: str
