from django.contrib import admin
from .models import Subscription, Plan


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'start_date', 'expire_date', 'next_payment_date', 'status', "scheduled_plan")
    list_filter = ('plan', 'status')
    search_fields = ('user__email',)


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'id', 'payment_plan_id', 'monthly_price', 'amount_products_per_week', "payment_plan_id", 'status')
    search_fields = ('name','payment_plan_id')
    list_filter = ('status', 'is_trial')

    def save_model(self, request, obj, form, change):
        super(PlanAdmin, self).save_model(request, obj, form, change)

        #! updating related products that assigning to user by subscription
        #! necessary only if diplayed or processed data must be synced beetwen models
        ###* move imports to top
        # # from django.db.models.functions import Left, Concat
        # # from django.db.models import F, CharField, Value
        # obj.plan_drops.filter(category__status=True).annotate(new_drop_id=Left('drop_id', 6))\
        #     .update(drop_id=Concat(F('new_drop_id'),
        #                             Value(obj.amount_products_per_week),
        #                             output_field=CharField()),
        #             drop_plan_size=Value(obj.amount_products_per_week))
        # obj.save()
