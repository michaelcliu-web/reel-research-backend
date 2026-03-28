from rest_framework import permissions


class IsAuthenticatedAndOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_authenticated:
            if request.method in permissions.SAFE_METHODS:
                return True
            return obj.user == request.user
        return False


class IsAuthenticatedAndOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_authenticated:
            return obj.user == request.user
        return False

    def has_permission(self, request, view):
        return self.has_object_permission(request, view, view.get_object())


class IsAuthenticatedAndOwnerUser(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_authenticated:
            return obj == request.user
        return False

    def has_permission(self, request, view):
        return self.has_object_permission(request, view, view.get_object())


class IsAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)
