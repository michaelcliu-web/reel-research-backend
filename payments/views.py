import stripe
from datetime import datetime
from django.conf import settings
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from api.models import CustomUser
from .models import Subscription

stripe.api_key = settings.STRIPE_SECRET_KEY


def report_to_sentry(error):
    try:
        import sentry_sdk
        sentry_sdk.capture_exception(error) if isinstance(error, Exception) else sentry_sdk.capture_message(str(error))
    except ImportError:
        pass


SUBSCRIPTION_PRICE_MAP = {
    'monthly': lambda: settings.STRIPE_MONTHLY_PRICE_ID,
    'yearly': lambda: settings.STRIPE_YEARLY_PRICE_ID,
}


def _get_user_subscription(user):
    return Subscription.objects.filter(user=user).first()


def _get_or_create_stripe_customer(user):
    subscription = _get_user_subscription(user)

    if subscription and subscription.stripe_customer_id:
        try:
            stripe.Customer.retrieve(subscription.stripe_customer_id)
            return subscription.stripe_customer_id
        except stripe.error.InvalidRequestError:
            pass

    customer = stripe.Customer.create(
        email=user.email,
        metadata={'user_id': str(user.id)}
    )

    Subscription.objects.update_or_create(
        user=user,
        defaults={
            'stripe_customer_id': customer.id,
            'status': 'pending',
        }
    )

    return customer.id


class StripeCheckoutView(APIView):
    """Create a Stripe checkout session for subscriptions."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = request.user
            subscription_type = request.data.get('subscription_type')
            success_url = request.data.get('success_url')
            cancel_url = request.data.get('cancel_url')

            if not success_url or not cancel_url:
                return Response(
                    {'error': 'success_url and cancel_url are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            customer_id = _get_or_create_stripe_customer(user)

            if subscription_type not in SUBSCRIPTION_PRICE_MAP:
                return Response(
                    {'error': f'Invalid subscription type. Must be one of: {list(SUBSCRIPTION_PRICE_MAP.keys())}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            existing_sub = _get_user_subscription(user)
            if existing_sub and existing_sub.status == 'active' and existing_sub.stripe_subscription_id:
                return Response(
                    {'error': 'You already have an active subscription. Manage it from your settings.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            price_id = SUBSCRIPTION_PRICE_MAP[subscription_type]()
            if not price_id:
                return Response(
                    {'error': 'This plan is not yet configured. Please contact support.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            checkout_session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{'price': price_id, 'quantity': 1}],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'user_id': str(user.id),
                    'payment_type': 'subscription',
                    'plan': subscription_type,
                },
                allow_promotion_codes=True,
            )

            return Response({
                'url': checkout_session.url,
                'session_id': checkout_session.id
            })

        except stripe.error.StripeError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {'error': 'An error occurred. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VerifyCheckoutSession(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        session_id = request.data.get('session_id')
        if not session_id:
            return Response(
                {'error': 'No session_id provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            session = stripe.checkout.Session.retrieve(session_id)

            if session.payment_status == 'paid':
                metadata = session.get('metadata', {})
                payment_type = metadata.get('payment_type')
                user = request.user

                if payment_type == 'subscription':
                    plan = metadata.get('plan', 'monthly')
                    stripe_subscription_id = session.get('subscription')
                    customer_id = session.get('customer')

                    sub_defaults = {
                        'stripe_customer_id': customer_id,
                        'plan': plan,
                        'status': 'active',
                    }

                    if stripe_subscription_id:
                        sub_defaults['stripe_subscription_id'] = stripe_subscription_id
                        try:
                            stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)
                            sub_defaults['stripe_price_id'] = stripe_sub['items']['data'][0]['price']['id']
                            sub_defaults['current_period_start'] = datetime.fromtimestamp(
                                stripe_sub['current_period_start']
                            )
                            sub_defaults['current_period_end'] = datetime.fromtimestamp(
                                stripe_sub['current_period_end']
                            )
                        except Exception:
                            pass

                    Subscription.objects.update_or_create(
                        user=user,
                        defaults=sub_defaults,
                    )

                    return Response({
                        'success': True,
                        'subscription': {
                            'plan': plan,
                            'status': 'active',
                            'is_active': True,
                        }
                    })

                return Response({'success': True})
            else:
                return Response(
                    {'error': 'Payment not completed'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        except stripe.error.StripeError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {'error': 'Failed to verify checkout session'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class StripeCancelSubscriptionView(APIView):
    """Cancel the current user's Stripe subscription at end of billing period."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            subscription = _get_user_subscription(request.user)

            if not subscription:
                return Response(
                    {'error': 'No subscription found.'},
                    status=status.HTTP_404_NOT_FOUND
                )

            stripe_subscription_id = subscription.stripe_subscription_id

            if not stripe_subscription_id and subscription.stripe_customer_id:
                subs = stripe.Subscription.list(
                    customer=subscription.stripe_customer_id,
                    status='active',
                    limit=1,
                )
                if subs.data:
                    stripe_subscription_id = subs.data[0].id
                    subscription.stripe_subscription_id = stripe_subscription_id
                    subscription.save()
                else:
                    return Response(
                        {'error': 'No active Stripe subscription found for your account.'},
                        status=status.HTTP_404_NOT_FOUND
                    )

            stripe_sub = stripe.Subscription.modify(
                stripe_subscription_id,
                cancel_at_period_end=True,
            )

            subscription.cancel_at_period_end = True
            subscription.save(update_fields=['cancel_at_period_end'])

            period_end_ts = None
            items_data = stripe_sub.get('items', {}).get('data', [])
            if items_data:
                period_end_ts = items_data[0].get('current_period_end')
            if not period_end_ts:
                period_end_ts = stripe_sub.get('current_period_end') or stripe_sub.get('cancel_at')

            if period_end_ts:
                period_end = datetime.fromtimestamp(period_end_ts)
                msg = f'Your subscription will be cancelled at the end of your billing period ({period_end.strftime("%B %d, %Y")}).'
            else:
                period_end = None
                msg = 'Your subscription will be cancelled at the end of your current billing period.'

            return Response({
                'success': True,
                'message': msg,
                'cancel_at_period_end': True,
                'current_period_end': period_end.isoformat() if period_end else None,
            })

        except stripe.error.StripeError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {'error': 'Failed to cancel subscription. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class StripeSwitchPlanView(APIView):
    """Switch between monthly and yearly billing."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            new_plan = request.data.get('plan')
            if new_plan not in SUBSCRIPTION_PRICE_MAP:
                return Response(
                    {'error': f'Invalid plan. Must be one of: {list(SUBSCRIPTION_PRICE_MAP.keys())}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            subscription = _get_user_subscription(request.user)
            if not subscription or not subscription.stripe_subscription_id:
                return Response(
                    {'error': 'No active subscription found.'},
                    status=status.HTTP_404_NOT_FOUND
                )

            new_price_id = SUBSCRIPTION_PRICE_MAP[new_plan]()
            stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
            item_id = stripe_sub['items']['data'][0].id

            updated_sub = stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                items=[{
                    'id': item_id,
                    'price': new_price_id,
                }],
                proration_behavior='create_prorations',
            )

            subscription.plan = new_plan
            subscription.stripe_price_id = new_price_id
            items_data = updated_sub.get('items', {}).get('data', [])
            if items_data:
                ps = items_data[0].get('current_period_start')
                pe = items_data[0].get('current_period_end')
                if ps:
                    subscription.current_period_start = datetime.fromtimestamp(ps)
                if pe:
                    subscription.current_period_end = datetime.fromtimestamp(pe)
            subscription.save()

            return Response({
                'success': True,
                'message': f'Switched to {new_plan}. Changes take effect immediately.',
                'plan': new_plan,
            })

        except stripe.error.StripeError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {'error': 'Failed to switch plan.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class StripeReactivateSubscriptionView(APIView):
    """Reactivate a subscription that was set to cancel at period end."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            subscription = _get_user_subscription(request.user)
            if not subscription or not subscription.stripe_subscription_id:
                return Response(
                    {'error': 'No subscription found to reactivate.'},
                    status=status.HTTP_404_NOT_FOUND
                )

            if not subscription.cancel_at_period_end:
                return Response(
                    {'error': 'Subscription is not scheduled for cancellation.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=False,
            )

            subscription.cancel_at_period_end = False
            subscription.save(update_fields=['cancel_at_period_end'])

            return Response({
                'success': True,
                'message': 'Your subscription has been reactivated.',
                'cancel_at_period_end': False,
            })

        except stripe.error.StripeError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {'error': 'Failed to reactivate subscription.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class StripePortalView(APIView):
    permission_classes = [IsAuthenticated]

    _portal_config_id = None

    @classmethod
    def _get_or_create_portal_config(cls):
        if cls._portal_config_id:
            return cls._portal_config_id

        price_ids = [
            pid for pid in [
                getattr(settings, 'STRIPE_MONTHLY_PRICE_ID', ''),
                getattr(settings, 'STRIPE_YEARLY_PRICE_ID', ''),
            ] if pid
        ]

        product_prices = {}
        for price_id in price_ids:
            price = stripe.Price.retrieve(price_id)
            product_id = price.product
            product_prices.setdefault(product_id, []).append(price_id)

        products_config = [
            {'product': prod, 'prices': prices}
            for prod, prices in product_prices.items()
        ]

        config = stripe.billing_portal.Configuration.create(
            business_profile={
                'headline': 'Manage your billing',
            },
            features={
                'subscription_update': {
                    'enabled': True,
                    'default_allowed_updates': ['price'],
                    'products': products_config,
                    'proration_behavior': 'create_prorations',
                },
                'subscription_cancel': {'enabled': False},
                'payment_method_update': {'enabled': True},
                'invoice_history': {'enabled': True},
            },
        )
        cls._portal_config_id = config.id
        return cls._portal_config_id

    def post(self, request):
        try:
            subscription = _get_user_subscription(request.user)
            if not subscription or not subscription.stripe_customer_id:
                return Response(
                    {'error': 'No payment record found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            config_id = self._get_or_create_portal_config()

            portal_session = stripe.billing_portal.Session.create(
                customer=subscription.stripe_customer_id,
                return_url=f"{settings.FRONTEND_URL.rstrip('/')}?from_portal=true",
                configuration=config_id,
            )

            return Response({'url': portal_session.url})

        except stripe.error.StripeError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhook(View):
    def post(self, request):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            return JsonResponse({'error': 'Invalid payload'}, status=400)
        except stripe.error.SignatureVerificationError:
            return JsonResponse({'error': 'Invalid signature'}, status=400)

        event_type = event['type']
        data = event['data']['object']

        if event_type == 'checkout.session.completed':
            self.handle_checkout_completed(data)
        elif event_type == 'customer.subscription.updated':
            self.handle_subscription_updated(data)
        elif event_type == 'customer.subscription.deleted':
            self.handle_subscription_deleted(data)
        elif event_type == 'invoice.payment_failed':
            self.handle_payment_failed(data)

        return JsonResponse({'status': 'success'})

    def _find_user(self, session):
        metadata = session.get('metadata', {})
        user_id = metadata.get('user_id')

        if user_id:
            try:
                return CustomUser.objects.get(id=user_id)
            except CustomUser.DoesNotExist:
                pass

        customer_email = (
            session.get('customer_details', {}).get('email')
            or session.get('customer_email')
        )
        if customer_email:
            try:
                return CustomUser.objects.get(email=customer_email)
            except CustomUser.DoesNotExist:
                pass

        return None

    def handle_checkout_completed(self, session):
        metadata = session.get('metadata', {})
        payment_type = metadata.get('payment_type')

        user = self._find_user(session)
        if not user:
            return

        if payment_type == 'subscription':
            plan = metadata.get('plan', 'monthly')
            stripe_subscription_id = session.get('subscription')

            sub_data = {
                'stripe_customer_id': session.get('customer'),
                'plan': plan,
                'status': 'active',
            }

            if stripe_subscription_id:
                sub_data['stripe_subscription_id'] = stripe_subscription_id
                try:
                    stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)
                    sub_data['stripe_price_id'] = stripe_sub['items']['data'][0]['price']['id']
                    sub_data['current_period_start'] = datetime.fromtimestamp(stripe_sub['current_period_start'])
                    sub_data['current_period_end'] = datetime.fromtimestamp(stripe_sub['current_period_end'])
                except Exception:
                    pass

            Subscription.objects.update_or_create(
                user=user,
                defaults=sub_data
            )

    @staticmethod
    def _infer_plan_from_price(price_id):
        mapping = {
            getattr(settings, 'STRIPE_MONTHLY_PRICE_ID', ''): 'monthly',
            getattr(settings, 'STRIPE_YEARLY_PRICE_ID', ''): 'yearly',
        }
        return mapping.get(price_id, None)

    def handle_subscription_updated(self, subscription):
        stripe_sub_id = subscription.get('id')
        stripe_status = subscription.get('status')
        cancel_at_period_end = subscription.get('cancel_at_period_end', False)

        try:
            sub = Subscription.objects.get(stripe_subscription_id=stripe_sub_id)
            sub.status = stripe_status
            sub.cancel_at_period_end = cancel_at_period_end
            sub.current_period_start = datetime.fromtimestamp(subscription['current_period_start'])
            sub.current_period_end = datetime.fromtimestamp(subscription['current_period_end'])

            if cancel_at_period_end and subscription.get('canceled_at'):
                sub.cancelled_at = datetime.fromtimestamp(subscription['canceled_at'])

            price_id = subscription['items']['data'][0]['price']['id']
            sub.stripe_price_id = price_id

            inferred_plan = self._infer_plan_from_price(price_id)
            if inferred_plan:
                sub.plan = inferred_plan

            sub.save()
        except Subscription.DoesNotExist:
            pass

    def handle_subscription_deleted(self, subscription):
        stripe_sub_id = subscription.get('id')
        try:
            sub = Subscription.objects.get(stripe_subscription_id=stripe_sub_id)
            sub.status = 'canceled'
            sub.save()
        except Subscription.DoesNotExist:
            pass

    def handle_payment_failed(self, invoice):
        stripe_sub_id = invoice.get('subscription')
        if not stripe_sub_id:
            return
        try:
            sub = Subscription.objects.get(stripe_subscription_id=stripe_sub_id)
            sub.status = 'past_due'
            sub.save()
        except Subscription.DoesNotExist:
            pass
