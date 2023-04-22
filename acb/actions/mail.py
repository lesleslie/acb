import os
from enum import Enum
from mimetypes import MimeTypes
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Union

# from config import debug
from fastapi import BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi_mail import ConnectionConfig
from fastapi_mail import FastMail
from fastapi_mail.email_utils import DefaultChecker
from fastapi_mail.errors import WrongFile
from starlette.datastructures import UploadFile

from pydantic import BaseModel
from pydantic import EmailStr
from pydantic import validator


# from fastapi import Request


class MultipartSubtypeEnum(Enum):
    """
    for more info about Multipart subtypes visit:
        https://en.wikipedia.org/wiki/MIME#Multipart_subtypes
    """

    mixed = "mixed"
    digest = "digest"
    alternative = "alternative"
    related = "related"
    report = "report"
    signed = "signed"
    encrypted = "encrypted"
    form_data = "form-data"
    mixed_replace = "x-mixed-replace"
    byterange = "byterange"


class MessageSchema(BaseModel):
    recipients: List[EmailStr]
    attachments: List[Union[UploadFile, Dict, str]] = []
    subject: str = ""
    body: Optional[Union[str, list]] = None
    template_body: Optional[Union[list, dict]] = None
    html: Optional[Union[str, List, Dict]] = None
    cc: List[EmailStr] = []
    bcc: List[EmailStr] = []
    reply_to: List[EmailStr] = []
    charset: str = "utf-8"
    subtype: Optional[str] = None
    multipart_subtype: MultipartSubtypeEnum = MultipartSubtypeEnum.mixed
    headers: Optional[Dict] = None

    @validator("attachments")
    def validate_file(cls, v):
        temp = []
        mime = MimeTypes()

        for file in v:
            file_meta = None
            if isinstance(file, dict):
                keys = file.keys()
                if "file" not in keys:
                    raise WrongFile('missing "file" key')
                file_meta = dict.copy(file)
                del file_meta["file"]
                file = file["file"]
            if isinstance(file, str):
                if (
                    os.path.isfile(file)
                    and os.access(file, os.R_OK)
                    and validate_path(file)
                ):
                    mime_type = mime.guess_type(file)
                    f = open(file, mode="rb")
                    _, file_name = os.path.split(f.name)
                    u = UploadFile(file_name, f, content_type=mime_type[0])
                    temp.append((u, file_meta))
                else:
                    raise WrongFile(
                        "incorrect file path for attachment or not readable"
                    )
            elif isinstance(file, UploadFile):
                temp.append((file, file_meta))
            else:
                raise WrongFile(
                    "attachments field type incorrect, must be UploadFile or path"
                )
        return temp

    @validator("subtype")
    def validate_subtype(cls, value, values, config, field):
        """Validate subtype field."""
        if values["template_body"]:
            return "html"
        return value

    class Config:
        arbitrary_types_allowed = True


def validate_path(path):
    cur_dir = os.path.abspath(os.curdir)
    requested_path = os.path.abspath(os.path.relpath(path, start=cur_dir))
    common_prefix = os.path.commonprefix([requested_path, cur_dir])
    return common_prefix == cur_dir


# message = MessageSchema(
#     subject="subject",
#     recipients=["list_of_recipients"],
#     body="Hello World",
#     cc=["list_of_recipients"],
#     bcc=["list_of_recipients"],
#     reply_to=["list_of_recipients"],
#     subtype="plain",
# )


class EmailSchema(BaseModel):
    email: list[EmailStr]
    body: Any


class Mail(BaseModel):
    # class Connection(ConnectionConfig):
    #     server = ac.mail.dict()[ac.app.mail_provider]["server"]
    #     template_engine = jinja_env
    #
    #     def __init__(self, **data: Any):
    #         super().__init__(**data)
    #         for k, v in {**ac.mail.dict(), **self.server}:
    #             setattr(self, f"mail_{k}".replace("default_", "").upper(), v)

    # @app.post("/email")
    @staticmethod
    async def send_with_template(email: EmailSchema) -> JSONResponse:
        message = MessageSchema(
            subject="Fastapi-Mail module",
            recipients=email.dict().get(
                "email"
            ),  # List of recipients, as many as you can pass
            template_body=email.dict().get("body"),
        )
        fm = FastMail(ConnectionConfig())
        await fm.send_message(message, template_name="email_template.html")
        return JSONResponse(status_code=200, content={"message": "email has been sent"})

    # @app.post("/emailbackground")
    @staticmethod
    async def send_in_background(
        background_tasks: BackgroundTasks, email: EmailSchema
    ) -> JSONResponse:
        message = MessageSchema(
            subject="Fastapi mail module",
            recipients=email.dict().get("email"),
            body="Simple background task",
        )
        fm = FastMail(ConnectionConfig())
        background_tasks.add_task(fm.send_message, message)
        return JSONResponse(status_code=200, content={"message": "email has been sent"})

    @staticmethod
    async def default_checker():
        checker = DefaultChecker(db_provider="redis")
        await checker.init_redis()
        return checker

    async def init(self):
        self.set_logger()


mail = Mail()
