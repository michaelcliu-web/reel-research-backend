from .models import CustomUser
from .serializers import CustomUserSerializer
from .permissions import IsAuthenticatedAndOwnerUser

from rest_framework import viewsets, mixins, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404


def report_to_sentry(error):
    try:
        import sentry_sdk
        sentry_sdk.capture_exception(error) if isinstance(error, Exception) else sentry_sdk.capture_message(str(error))
    except ImportError:
        pass


class CustomUserViewSet(
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer
    lookup_field = "id"

    @action(detail=False, methods=["GET"])
    def me(self, request):
        try:
            return Response(
                status=status.HTTP_200_OK,
                data=CustomUserSerializer(request.user).data,
            )
        except Exception as e:
            report_to_sentry(e)
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={"message": "Something went wrong while fetching your user data."},
            )

    @action(detail=True, methods=["POST"])
    def edit(self, request, id):
        try:
            user = get_object_or_404(CustomUser, clerk_id=id)

            if "first_name" in request.data:
                user.first_name = request.data["first_name"]
            if "last_name" in request.data:
                user.last_name = request.data["last_name"]
            if "email" in request.data:
                user.email = request.data["email"]

            user.save()

            return Response(
                status=status.HTTP_200_OK,
                data={"message": "User updated successfully."},
            )
        except Exception as e:
            report_to_sentry(e)
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={"message": "Something went wrong while updating the user."},
            )

    def get_permissions(self):
        permissions = []
        if self.request.user.is_superuser:
            return [AllowAny()]
        if self.action == "retrieve" or self.action == "destroy":
            permissions.append(IsAuthenticatedAndOwnerUser())
        return permissions

    def get_queryset(self):
        return super().get_queryset()
