from rest_framework import routers
from .viewsets import CustomUserViewSet

router = routers.DefaultRouter()
router.register(r"users", CustomUserViewSet)

urlpatterns = []
urlpatterns += router.urls
