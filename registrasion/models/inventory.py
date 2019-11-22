import datetime

from django.db import models
from django.contrib.postgres.fields import JSONField
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _


# Inventory Models

@python_2_unicode_compatible
class Category(models.Model):
    ''' Registration product categories, used as logical groupings for Products
    in registration forms.

    Attributes:
        name (str): The display name for the category.

        description (str): Some explanatory text for the category. This is
            displayed alongside the forms where your attendees choose their
            items.

        required (bool): Requires a user to select an item from this category
            during initial registration. You can use this, e.g., for making
            sure that the user has a ticket before they select whether they
            want a t-shirt.

        render_type (int): This is used to determine what sort of form the
            attendee will be presented with when choosing Products from this
            category. These may be either of the following:

            ``RENDER_TYPE_RADIO`` presents the Products in the Category as a
            list of radio buttons. At most one item can be chosen at a time.
            This works well when setting limit_per_user to 1.

            ``RENDER_TYPE_QUANTITY`` shows each Product next to an input field,
            where the user can specify a quantity of each Product type. This is
            useful for additional extras, like Dinner Tickets.

            ``RENDER_TYPE_ITEM_QUANTITY`` shows a select menu to select a
            Product type, and an input field, where the user can specify the
            quantity for that Product type. This is useful for categories that
            have a lot of options, from which the user is not going to select
            all of the options.

            ``RENDER_TYPE_CHECKBOX`` shows a checkbox beside each product.

            ``RENDER_TYPE_PWYW`` adds a freeform amount field for users to
            pay what they want.

            ``RENDER_TYPE_PWYW_QUANTITY`` adds a freeform amount field for users
            to pay what they want and select a quantity.

            ``RENDER_TYPE_CHECKBOX_QUANTITY`` similar to RENDER_TYPE_QUANTITY
            but displays products with a limit of 1 as a checkbox.

        limit_per_user (Optional[int]): This restricts the number of items
            from this Category that each attendee may claim. This extends
            across multiple Invoices.

        order (int): An ascending order for displaying the Categories
            available. By convention, your Category for ticket types should
            have the lowest display order.
    '''

    class Meta:
        app_label = "registrasion"
        verbose_name = _("inventory - category")
        verbose_name_plural = _("inventory - categories")
        ordering = ("order", )

    def __str__(self):
        return self.name

    RENDER_TYPE_RADIO = 1
    RENDER_TYPE_QUANTITY = 2
    RENDER_TYPE_ITEM_QUANTITY = 3
    RENDER_TYPE_CHECKBOX = 4
    RENDER_TYPE_PWYW = 5
    RENDER_TYPE_CHECKBOX_QUANTITY = 6
    RENDER_TYPE_PWYW_QUANTITY = 7
    RENDER_TYPE_CHILDCARE = 8
    RENDER_TYPE_YOUNGCODERS = 9

    CATEGORY_RENDER_TYPES = [
        (RENDER_TYPE_RADIO, _("Radio button")),
        (RENDER_TYPE_QUANTITY, _("Quantity boxes")),
        (RENDER_TYPE_ITEM_QUANTITY, _("Product selector and quantity box")),
        (RENDER_TYPE_CHECKBOX, _("Checkbox button")),
        (RENDER_TYPE_PWYW, _("User Selected Amount")),
        (RENDER_TYPE_PWYW_QUANTITY, _("User Selected Amount and quantity box")),
        (RENDER_TYPE_CHECKBOX_QUANTITY, _("Checkbox/Quantity Hybrid")),
        (RENDER_TYPE_CHILDCARE, _("Childcare with additional info")),
        (RENDER_TYPE_YOUNGCODERS, _("YoungCoders with additional info")),
    ]

    name = models.CharField(
        max_length=255,
        verbose_name=_("Name"),
    )
    description = models.TextField(
        verbose_name=_("Description"),
    )
    limit_per_user = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Limit per user"),
        help_text=_("The total number of items from this category one "
                    "attendee may purchase."),
    )
    required = models.BooleanField(
        blank=True,
        help_text=_("If enabled, a user must select an "
                    "item from this category."),
    )
    order = models.PositiveIntegerField(
        verbose_name=("Display order"),
        db_index=True,
    )
    render_type = models.IntegerField(
        choices=CATEGORY_RENDER_TYPES,
        verbose_name=_("Render type"),
        help_text=_("The registration form will render this category in this "
                    "style."),
    )
    form_css_class = models.CharField(
        verbose_name=_("CSS Class for container holding product fields"),
        max_length=512, null=True, blank=True,
    )
    product_css_class = models.CharField(
        verbose_name=_("CSS Class for each product field"),
        max_length=512, null=True, blank=True,
    )


@python_2_unicode_compatible
class Product(models.Model):
    ''' Products make up the conference inventory.

    Attributes:
        name (str): The display name for the product.

        description (str): Some descriptive text that will help the user to
            understand the product when they're at the registration form.

        category (Category): The Category that this product will be grouped
            under.

        price (Decimal): The price that 1 unit of this product will sell for.
            Note that this should be the full price, before any discounts are
            applied.

        limit_per_user (Optional[int]): This restricts the number of this
            Product that each attendee may claim. This extends across multiple
            Invoices.

        reservation_duration (datetime): When a Product is added to the user's
            tentative registration, it is marked as unavailable for a period of
            time. This allows the user to build up their registration and then
            pay for it. This reservation duration determines how long an item
            should be allowed to be reserved whilst being unpaid.

        order (int): An ascending order for displaying the Products
            within each Category.

    '''

    class Meta:
        app_label = "registrasion"
        verbose_name = _("inventory - product")
        ordering = ("category__order", "order")

    def __str__(self):
        return "%s - %s" % (self.category.name, self.name)

    name = models.CharField(
        max_length=255,
        verbose_name=_("Name"),
    )
    description = models.TextField(
        verbose_name=_("Description"),
        null=True,
        blank=True,
    )
    category = models.ForeignKey(
        Category,
        verbose_name=_("Product category"),
        on_delete=models.CASCADE,
    )
    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        verbose_name=_("Price"),
    )
    pay_what_you_want = models.BooleanField(
        verbose_name=("Pay What You Want"),
        default=False,
    )
    limit_per_user = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Limit per user"),
    )
    reservation_duration = models.DurationField(
        default=datetime.timedelta(hours=1),
        verbose_name=_("Reservation duration"),
        help_text=_("The length of time this product will be reserved before "
                    "it is released for someone else to purchase."),
    )
    order = models.PositiveIntegerField(
        verbose_name=("Display order"),
        db_index=True,
    )
    display_price = models.BooleanField(
        verbose_name=("Display price"),
        default=True,
    )
    hide_line_item = models.BooleanField(
        verbose_name=("Hide LineItem"),
        default=False,
    )
    additional_data = JSONField(null=True, blank=True)

    allow_housing = models.BooleanField(
        verbose_name=("Allow Housing Registration"),
        default=False,
    )

    is_donation = models.BooleanField(
        default=False,
    )


@python_2_unicode_compatible
class Voucher(models.Model):
    ''' Vouchers are used to enable Discounts or Flags for the people who hold
    the voucher code.

    Attributes:
        recipient (str): A display string used to identify the holder of the
            voucher on the admin page.

        code (str): The string that is used to prove that the attendee holds
            this voucher.

        limit (int): The number of attendees who are permitted to hold this
            voucher.

     '''

    class Meta:
        app_label = "registrasion"

    # Vouchers reserve a cart for a fixed amount of time, so that
    # items may be added without the voucher being swiped by someone else
    RESERVATION_DURATION = datetime.timedelta(hours=1)

    def __str__(self):
        return "Voucher for %s" % self.recipient

    @classmethod
    def normalise_code(cls, code):
        return code.upper()

    def save(self, *a, **k):
        ''' Normalise the voucher code to be uppercase '''
        self.code = self.normalise_code(self.code)
        super(Voucher, self).save(*a, **k)

    recipient = models.CharField(max_length=128, verbose_name=_("Recipient"))
    code = models.CharField(max_length=32,
                            unique=True,
                            verbose_name=_("Voucher code"))
    limit = models.PositiveIntegerField(verbose_name=_("Voucher use limit"))
