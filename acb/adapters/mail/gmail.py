from . import MailBaseSettings
from . import MailBase


class MailSettings(MailBaseSettings):
    mx_servers: list[str] = [
        "1 aspmx.l.google.com.",
        "5 alt1.aspmx.l.google.com.",
        "5 alt2.aspmx.l.google.com.",
        "10 alt3.aspmx.l.google.com.",
        "10 alt4.aspmx.l.google.com.",
    ]


class Mail(MailBase):
    ...


mail: Mail = Mail()
