# app/api/v1/endpoints/oauth.py

from fastapi import APIRouter, Request
from authlib.integrations.starlette_client import OAuth
from starlette.responses import RedirectResponse
from app.core.config import settings
from app.db.session import users_collection
from app.core.security import create_access_token

router = APIRouter()
oauth = OAuth()

oauth.register(
    name='google',
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

oauth.register(
    name='github',
    client_id=settings.GITHUB_CLIENT_ID,
    client_secret=settings.GITHUB_CLIENT_SECRET,
    access_token_url='https://github.com/login/oauth/access_token',
    authorize_url='https://github.com/login/oauth/authorize',
    api_base_url='https://api.github.com/',
    client_kwargs={'scope': 'user:email'},
)

@router.get('/login/{provider}')
async def login_via_provider(request: Request, provider: str):
    redirect_uri = request.url_for('auth_callback', provider=provider)
    return await oauth.create_client(provider).authorize_redirect(request, redirect_uri)

@router.get('/auth/{provider}')
async def auth_callback(request: Request, provider: str):
    token = await oauth.create_client(provider).authorize_access_token(request)
    user_info = token.get('userinfo')
    if not user_info:
        # For GitHub, you need to make an additional request to get user info
        resp = await oauth.github.get('user', token=token)
        user_info = resp.json()
        # To get the primary email for GitHub
        if not user_info.get('email'):
            emails = await oauth.github.get('user/emails', token=token)
            email_info = next((e for e in emails.json() if e['primary']), emails.json()[0])
            user_info['email'] = email_info['email']

    email = user_info['email']
    user = await users_collection.find_one({"email": email})

    if not user:
        # If the user doesn't exist, create a new one.
        # Note: You might want to generate a random password or mark the user as an OAuth user.
        new_user = {"email": email, "hashed_password": ""}
        await users_collection.insert_one(new_user)

    # Create an access token for the user
    access_token = create_access_token(data={"sub": email})

    # Redirect the user to the frontend with the token
    response = RedirectResponse(url=f"/dashboard?token={access_token}")
    response.set_cookie(key="token", value=access_token) # Or set a cookie
    return response