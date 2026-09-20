import json

from django.contrib.auth import authenticate, get_user_model
from django.conf import settings
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken


REFRESH_COOKIE = "angelai_refresh"
User = get_user_model()


def _json_body(request):
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return None


def _tokens_for(user):
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token), str(refresh)


def _set_refresh_cookie(response, refresh_token):
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=7 * 24 * 60 * 60,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="Lax" if settings.DEBUG else "None",
    )
    return response


@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    body = _json_body(request)
    username = (body or {}).get("username", "").strip()
    password = (body or {}).get("password", "")

    if not username or not password:
        return JsonResponse({"error": "username and password are required."}, status=400)
    if len(password) < 8:
        return JsonResponse({"error": "password must be at least 8 characters."}, status=400)
    if User.objects.filter(username=username).exists():
        return JsonResponse({"error": "username is already registered."}, status=409)

    user = User.objects.create_user(username=username, password=password)
    access_token, refresh_token = _tokens_for(user)
    response = JsonResponse({"access": access_token, "username": user.username}, status=201)
    return _set_refresh_cookie(response, refresh_token)


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    body = _json_body(request)
    username = (body or {}).get("username", "").strip()
    password = (body or {}).get("password", "")
    user = authenticate(request, username=username, password=password)
    if user is None:
        return JsonResponse({"error": "Invalid username or password."}, status=401)

    access_token, refresh_token = _tokens_for(user)
    response = JsonResponse({"access": access_token, "username": user.username})
    return _set_refresh_cookie(response, refresh_token)


@api_view(["POST"])
@permission_classes([AllowAny])
def refresh(request):
    body = _json_body(request) or {}
    refresh_token = request.COOKIES.get(REFRESH_COOKIE) or body.get("refresh")
    if not refresh_token:
        return JsonResponse({"error": "Refresh token is required."}, status=401)

    try:
        refresh_token_obj = RefreshToken(refresh_token)
        access_token = str(refresh_token_obj.access_token)
        if refresh_token_obj.get("jti"):
            refresh_token_obj.blacklist()
        new_refresh = RefreshToken.for_user(User.objects.get(id=refresh_token_obj["user_id"]))
    except (TokenError, User.DoesNotExist, KeyError):
        return JsonResponse({"error": "Invalid or expired refresh token."}, status=401)

    response = JsonResponse({"access": access_token})
    return _set_refresh_cookie(response, str(new_refresh))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    refresh_token = request.COOKIES.get(REFRESH_COOKIE) or (_json_body(request) or {}).get("refresh")
    if refresh_token:
        try:
            RefreshToken(refresh_token).blacklist()
        except TokenError:
            pass
    response = JsonResponse({"message": "Logged out."})
    response.delete_cookie(REFRESH_COOKIE)
    return response