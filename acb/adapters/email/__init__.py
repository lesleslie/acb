from acb.config import import_adapter

required_adapters = ["requests"]

Mail, MailSettings = import_adapter()
