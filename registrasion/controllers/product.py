import itertools

from django.db.models import Case
from django.db.models import F, Q
from django.db.models import Sum
from django.db.models import When
from django.db.models import Value

from registrasion.models import commerce
from registrasion.models import inventory

from .batch import BatchController
from .category import CategoryController
from .flag import FlagController
from .item import ItemController


def presentations_conflict(p0, p1):
    return (p0.slot.start_datetime <= p1.slot.end_datetime) and (p0.slot.end_datetime >= p1.slot.start_datetime)

class ProductController(object):

    def __init__(self, product):
        self.product = product

    @classmethod
    def available_products(cls, user, category=None, products=None):
        ''' Returns a list of all of the products that are available per
        flag conditions from the given categories. '''
        if category is None and products is None:
            raise ValueError("You must provide products or a category")

        if category is not None:
            all_products = inventory.Product.objects.filter(category=category)
            all_products = all_products.select_related("category")
        else:
            all_products = []

        if products is not None:
            all_products = set(itertools.chain(all_products, products))

        category_remainders = CategoryController.user_remainders(user)
        product_remainders = ProductController.user_remainders(user)

        passed_limits = set(
            product
            for product in all_products
            if category_remainders[product.category.id] > 0
            if product_remainders[product.id] > 0
        )

        failed_and_messages = FlagController.test_flags(
            user, products=passed_limits
        )
        failed_conditions = set(i[0] for i in failed_and_messages)

        out = list(passed_limits - failed_conditions)
        out.sort(key=lambda product: product.order)

        return out

    @classmethod
    def sold_out_products(cls, user, category=None, products=None):
        ''' Returns a list of all of the products that are available per
        flag conditions from the given categories... but sold out '''
        if category is None and products is None:
            raise ValueError("You must provide products or a category")

        if category is not None:
            all_products = inventory.Product.objects.filter(category=category)
            all_products = all_products.select_related("category")
        else:
            all_products = []

        if products is not None:
            all_products = set(itertools.chain(all_products, products))

        category_remainders = CategoryController.user_remainders(user)
        product_remainders = ProductController.user_remainders(user)

        passed_limits = set(
            product
            for product in all_products
            if category_remainders[product.category.id] > 0
            if product_remainders[product.id] > 0
        )

        failed_and_messages = FlagController.test_flags(
            user, products=passed_limits
        )
        failed_conditions = set()
        for product, message in failed_and_messages:
            product_time_or_stock_flags = product.flagbase_set.select_subclasses().exclude(timeorstocklimitflag__isnull=True).all()
            category_time_or_stock_flags = product.category.flagbase_set.select_subclasses().exclude(timeorstocklimitflag__isnull=True).all()
            if (
                any([bool(x.limit) for x in product_time_or_stock_flags]) or
                any([bool(x.limit) for x in category_time_or_stock_flags])
            ):
                failed_conditions.add(product)

        out = list(passed_limits.intersection(failed_conditions))
        out.sort(key=lambda product: product.order)

        return out

    @classmethod
    def disabled_products(cls, user, category=None, products=None):
        conflicting_products = inventory.Product.objects.exclude(presentation__isnull=True)
        purchased_products = [pq.product for pq in ItemController(user).items_purchased() if pq.product.presentation is not None]
        pending_products = [pq.product for pq in ItemController(user).items_pending() if pq.product.presentation is not None]
        return {
            'purchased': [p for p in conflicting_products if any(presentations_conflict(p.presentation, x.presentation) for x in purchased_products) and p not in purchased_products],
            'pending': [p for p in conflicting_products if any(presentations_conflict(p.presentation, x.presentation) for x in pending_products) and p not in pending_products],
        }

    @classmethod
    @BatchController.memoise
    def user_remainders(cls, user):
        '''

        Return:
            Mapping[int->int]: A dictionary that maps the product ID to the
            user's remainder for that product.
        '''

        products = inventory.Product.objects.all()

        cart_filter = (
            Q(productitem__cart__user=user) &
            Q(productitem__cart__status=commerce.Cart.STATUS_PAID)
        )

        quantity = When(
            cart_filter,
            then='productitem__quantity'
        )

        quantity_or_zero = Case(
            quantity,
            default=Value(0),
        )

        remainder = Case(
            When(limit_per_user=None, then=Value(99999999)),
            default=F('limit_per_user') - Sum(quantity_or_zero),
        )

        products = products.annotate(remainder=remainder)

        return dict((product.id, product.remainder) for product in products)
