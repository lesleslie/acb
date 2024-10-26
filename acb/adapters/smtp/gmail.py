import typing as t

from acb.depends import depends
from ._base import EmailBase, EmailBaseSettings


class EmailSettings(EmailBaseSettings):
    def model_post_init(self, __context: t.Any) -> None:
        del __context
        self.mx_servers = [
            "1 aspmx.l.google.com.",
            "5 alt1.aspmx.l.google.com.",
            "5 alt2.aspmx.l.google.com.",
            "10 alt3.aspmx.l.google.com.",
            "10 alt4.aspmx.l.google.com.",
        ]


class Email(EmailBase): ...


depends.set(Email)
