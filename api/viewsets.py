from payments.models import Subscription
from django.utils import timezone
from datetime import datetime, timedelta
import stripe
from django.conf import settings

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

    @action(detail=False, methods=["GET"])
    def subscription(self, request):
        """Get the current user's subscription data."""
        try:
            subscription = Subscription.objects.get(user=request.user)

            if subscription.status == 'pending':
                if subscription.created_at < timezone.now() - timedelta(hours=1):
                    subscription.delete()
                    return Response({
                        'plan': None,
                        'status': 'inactive',
                        'is_active': False,
                        'is_admin': request.user.is_superuser,
                        'cancel_at_period_end': False,
                        'current_period_end': None,
                    })

                return Response({
                    'id': str(subscription.id),
                    'plan': None,
                    'status': 'pending',
                    'is_active': False,
                    'is_admin': request.user.is_superuser,
                    'cancel_at_period_end': False,
                    'cancelled_at': None,
                    'usage_reset_date': None,
                    'created_at': subscription.created_at.isoformat() if subscription.created_at else None,
                    'stripe_subscription_id': None,
                    'stripe_customer_id': subscription.stripe_customer_id,
                    'current_period_start': None,
                    'current_period_end': None,
                })

            if not subscription.stripe_subscription_id and subscription.stripe_customer_id:
                try:
                    stripe.api_key = settings.STRIPE_SECRET_KEY
                    subs = stripe.Subscription.list(
                        customer=subscription.stripe_customer_id,
                        status='active',
                        limit=1,
                    )
                    if subs.data:
                        subscription.stripe_subscription_id = subs.data[0].id
                        price_id = subs.data[0]['items']['data'][0]['price']['id']
                        subscription.stripe_price_id = price_id
                        if not subscription.plan:
                            if price_id == getattr(settings, 'STRIPE_MONTHLY_PRICE_ID', ''):
                                subscription.plan = 'monthly'
                            elif price_id == getattr(settings, 'STRIPE_YEARLY_PRICE_ID', ''):
                                subscription.plan = 'yearly'
                            else:
                                subscription.plan = 'monthly'
                        subscription.status = 'active'
                        subscription.save()
                    else:
                        if subscription.status == 'active' and not subscription.stripe_subscription_id:
                            subscription.status = 'pending'
                            subscription.save()
                except Exception:
                    pass

            response_data = {
                'id': str(subscription.id),
                'plan': subscription.plan,
                'status': subscription.status,
                'is_active': subscription.is_active,
                'is_admin': request.user.is_superuser,
                'cancel_at_period_end': subscription.cancel_at_period_end,
                'cancelled_at': subscription.cancelled_at.isoformat() if subscription.cancelled_at else None,
                'usage_reset_date': subscription.usage_reset_date.isoformat() if subscription.usage_reset_date else None,
                'created_at': subscription.created_at.isoformat() if subscription.created_at else None,
                'stripe_subscription_id': subscription.stripe_subscription_id,
                'stripe_customer_id': subscription.stripe_customer_id,
                'current_period_start': subscription.current_period_start.isoformat() if subscription.current_period_start else None,
                'current_period_end': subscription.current_period_end.isoformat() if subscription.current_period_end else None,
            }

            if subscription.stripe_subscription_id:
                try:
                    stripe.api_key = settings.STRIPE_SECRET_KEY
                    stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)

                    if stripe_sub:
                        response_data['status'] = stripe_sub.get('status', subscription.status)
                        response_data['cancel_at_period_end'] = stripe_sub.get('cancel_at_period_end', False)

                        period_start = None
                        period_end = None
                        items_data = stripe_sub.get('items', {}).get('data', [])
                        if items_data:
                            period_start = items_data[0].get('current_period_start')
                            period_end = items_data[0].get('current_period_end')
                            current_price_id = items_data[0].get('price', {}).get('id')
                        else:
                            current_price_id = None

                        if current_price_id:
                            price_plan_map = {
                                getattr(settings, 'STRIPE_MONTHLY_PRICE_ID', ''): 'monthly',
                                getattr(settings, 'STRIPE_YEARLY_PRICE_ID', ''): 'yearly',
                            }
                            inferred_plan = price_plan_map.get(current_price_id)
                            if inferred_plan:
                                subscription.plan = inferred_plan
                                subscription.stripe_price_id = current_price_id
                                response_data['plan'] = inferred_plan

                        if not period_start:
                            period_start = stripe_sub.get('current_period_start') or stripe_sub.get('start_date')
                        if not period_end:
                            period_end = stripe_sub.get('current_period_end')

                        if period_start:
                            dt_start = datetime.fromtimestamp(period_start)
                            response_data['current_period_start'] = dt_start.isoformat()
                            subscription.current_period_start = dt_start

                        if period_end:
                            dt_end = datetime.fromtimestamp(period_end)
                            response_data['current_period_end'] = dt_end.isoformat()
                            subscription.current_period_end = dt_end

                        if stripe_sub.get('cancel_at'):
                            dt_cancel = datetime.fromtimestamp(stripe_sub['cancel_at'])
                            response_data['cancel_at'] = dt_cancel.isoformat()
                            response_data['current_period_end'] = dt_cancel.isoformat()
                            subscription.current_period_end = dt_cancel

                        if stripe_sub.get('canceled_at'):
                            response_data['canceled_at'] = datetime.fromtimestamp(stripe_sub['canceled_at']).isoformat()
                            subscription.cancelled_at = datetime.fromtimestamp(stripe_sub['canceled_at'])

                        response_data['is_active'] = stripe_sub.get('status') == 'active' and not stripe_sub.get('cancel_at_period_end', False)

                        subscription.status = stripe_sub.get('status', subscription.status)
                        subscription.cancel_at_period_end = stripe_sub.get('cancel_at_period_end', False)
                        subscription.save()

                except stripe.error.InvalidRequestError:
                    subscription.stripe_subscription_id = None
                    subscription.status = 'canceled'
                    subscription.save()
                    response_data['status'] = 'canceled'
                    response_data['is_active'] = False
                    response_data['stripe_subscription_id'] = None
                except Exception as e:
                    report_to_sentry(e)

            return Response(response_data)

        except Subscription.DoesNotExist:
            return Response({
                'plan': None,
                'status': 'inactive',
                'is_active': False,
                'is_admin': request.user.is_superuser,
                'cancel_at_period_end': False,
                'current_period_end': None,
            })
        except Exception as e:
            report_to_sentry(e)
            return Response(
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                data={"message": "Error retrieving subscription data"}
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
