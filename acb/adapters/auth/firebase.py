import typing as t
from contextlib import suppress
from datetime import timedelta
from time import time

from actions.log import ic
from actions.minify import minify
from adapters.database import db
from config import ac
from sqladmin.authentication import AuthenticationBackend
from sqlmodel import select
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request

from firebase_admin import auth
from firebase_admin import initialize_app as firebase_initialize_app
from google.auth.transport import requests as google_requests
from pydantic import BaseModel

# Verify the ID token first.
# claims = auth.verify_id_token(id_token)
# if claims['admin'] is True:
#     # Allow access to requested admin resource.
#     pass

# # Lookup the user associated with the specified uid.
# user = auth.get_user(uid)
# # The claims can be accessed on the user record.
# print(user.custom_claims.get('admin'))


firebase_request_adapter = google_requests.Request()
firebase_options = dict(projectId=ac.app.project)
firebase_app = firebase_initialize_app(options=dict(**firebase_options))


class CurrentUser(BaseModel):
    user_data: t.Any = dict()

    def has_role(self, role):
        return self.user_data.custom_claims.get(role)

    def set_role(self, role):
        return auth.set_custom_user_claims(self.user_data["uid"], {role: True})

    @property
    def is_admin(self):
        return self.user_data.get("admin")

    @property
    def is_owner(self):
        return self.user_data.get("owner")

    @property
    def is_contributor(self):
        return self.user_data.get("contributor")

    @property
    def is_superuser(self):
        return not self.user_data.get("user")

    @property
    def uid(self):
        return self.user_data.get("uid")

    @property
    def name(self):
        return self.user_data.get("name")

    @property
    def email(self):
        return self.user_data.get("email")

    def verify(self, request: Request = None) -> t.Any:
        if request:
            with suppress(auth.InvalidSessionCookieError):
                session_cookie = request.session.get(ac.firebase.token.id)
                if session_cookie:
                    user_data = auth.verify_session_cookie(
                        session_cookie, check_revoked=True
                    )
                    if user_data:
                        if ac.debug.firebase:
                            ic(user_data["name"])
                        self.user_data = user_data
        if self.user_data:
            if ac.debug.firebase:
                ic(self.name)
                ic(self.is_admin)
                ic(self.is_owner)
                ic(self.is_contributor)
            return self.user_data["uid"]
        return False


current_user = CurrentUser()


class AppAuthBackend(AuthenticationBackend):
    def __init__(self, secret_key: str, user_model: t.Any) -> None:
        super().__init__(secret_key)
        self.middlewares = [
            Middleware(
                SessionMiddleware,
                secret_key=secret_key,
                session_cookie=ac.firebase.token.session,
                https_only=True if ac.app.is_deployed else False,
            )
        ]
        self.name = "firebase"
        self.user_model = user_model
        # self.base_logger = BaseLogger()
        # self.ic = self.base_logger.ic
        # self.pf = self.base_logger.pf

    async def login(self, request: Request) -> bool:
        id_token = request.cookies.get(ac.firebase.token.id)
        user_data = None
        if id_token:
            if current_user.verify(request):
                return True
            try:
                user_data = auth.verify_id_token(id_token, check_revoked=True)
            except auth.RevokedIdTokenError:
                # Token revoked, inform the user to reauthenticate or signOut().
                pass
            except auth.UserDisabledError:
                # Token belongs to a disabled user record.
                pass
            except auth.InvalidIdTokenError:
                # Token is invalid
                pass
            if user_data:
                if debug.firebase:
                    await pf(user_data)
                async with db.async_session() as session:
                    user_query = select(self.user_model).where(
                        self.user_model.gmail == user_data["email"]
                        and self.user_model.is_active
                    )
                    result = await session.execute(user_query)
                    enabled_user = result.one_or_none()
                    await pf(enabled_user)
                if enabled_user and (time() - user_data["auth_time"] < 5 * 6):
                    enabled_user = enabled_user[0]
                    short_url = await minify.url(user_data["picture"])
                    # if debug.firebase:
                    #     ic(enabled_user.role)
                    #     await pf(short_url)
                    auth.set_custom_user_claims(
                        user_data["uid"], {enabled_user.role: True}
                    )
                    async with db.async_session() as session:
                        enabled_user.name = (user_data["name"],)
                        enabled_user.uid = (user_data["uid"],)
                        enabled_user.image = (short_url,)
                        await enabled_user.save()
                        # session.add(enabled_user)
                        # await session.commit()
                    expires_in = timedelta(days=14)
                    session_cookie = auth.create_session_cookie(
                        id_token, expires_in=expires_in
                    )
                    request.session.update({ac.firebase.token.id: session_cookie})
                    if debug.firebase:
                        ic(request.session.keys())
                    return True
                else:
                    auth.revoke_refresh_tokens(user_data["uid"])
        request.session.clear()
        current_user.user_data = dict()
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        with suppress(
            auth.ExpiredIdTokenError, auth.RevokedIdTokenError, auth.InvalidIdTokenError
        ):
            id_token = request.cookies.get(ac.firebase.token.id)
            user_data = auth.verify_id_token(id_token, check_revoked=True)
            auth.revoke_refresh_tokens(user_data["uid"])
        current_user.user_data = dict()
        return True

    async def authenticate(self, request: Request) -> bool:
        return current_user.verify(request)
