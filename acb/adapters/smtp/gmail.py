import typing as t

from acb.depends import depends

from ._base import SmtpBase, SmtpBaseSettings


class SmtpSettings(SmtpBaseSettings):
    def model_post_init(self, __context: t.Any) -> None:  # noqa: F841
        self.mx_servers = [
            "1 aspmx.l.google.com.",
            "5 alt1.aspmx.l.google.com.",
            "5 alt2.aspmx.l.google.com.",
            "10 alt3.aspmx.l.google.com.",
            "10 alt4.aspmx.l.google.com.",
        ]


class Smtp(SmtpBase): ...


depends.set(Smtp)
